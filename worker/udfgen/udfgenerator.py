import inspect
import ast
from textwrap import indent
from textwrap import dedent
from string import Template

import astor

from worker.udfgen import Table
from worker.udfgen import LiteralParameter
from worker.udfgen import LoopbackTable
from worker.udfgen.udfparams import SQLTYPES


UDF_REGISTER = {}


class UDFGenerator:
    _udftemplate = Template(
        """CREATE OR REPLACE FUNCTION
$func_name($input_params)
RETURNS
$output_expr
LANGUAGE PYTHON
{
    import numpy as np
    from arraybundle import ArrayBundle
    ___columns = _columns
    del _columns
$table_defs
$loopbacks
$literals

    # method body
$body
$return_stmt
};
"""
    )
    _returntemplate = Template(
        """
___colrange = range(${return_name}.shape[1])
___names = (f"${return_name}_{i}" for i in ___colrange)
___result = {n: c for n, c in zip(___names, ${return_name})}
return ___result"""
    )

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.code = inspect.getsource(func)
        self.tree = ast.parse(self.code)
        self.body = self._get_body()
        self.return_name = self._get_return_name()
        self.signature = inspect.signature(func)
        self.tableparams = [
            name
            for name, param in self.signature.parameters.items()
            if param.annotation == Table
        ]
        self.literalparams = [
            name
            for name, param in self.signature.parameters.items()
            if param.annotation == LiteralParameter
        ]
        self.loopbackparams = [
            name
            for name, param in self.signature.parameters.items()
            if param.annotation == LoopbackTable
        ]

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def _get_return_name(self):
        body_stmts = self.tree.body[0].body
        ret_stmt = next(s for s in body_stmts if isinstance(s, ast.Return))
        if isinstance(ret_stmt.value, ast.Name):
            ret_name = ret_stmt.value.id
        else:
            raise NotImplementedError("No expressions in return stmt, for now")
        return ret_name

    def _get_body(self):
        statemets = [
            stmt for stmt in self.tree.body[0].body if type(stmt) != ast.Return
        ]
        body = dedent("\n".join(astor.to_source(stmt) for stmt in statemets))
        return body

    def to_sql(self, *args, **kwargs):
        # verify types
        allowed = (Table, LiteralParameter, LoopbackTable)
        args_are_allowed = [type(ar) in allowed for ar in args + tuple(kwargs.values())]
        if not all(args_are_allowed):
            msg = f"Can't convert to SQL: all arguments must have types in {allowed}"
            raise TypeError(msg)

        # get inputs and output
        argnames = [
            name
            for name in self.signature.parameters.keys()
            if name not in kwargs.keys()
        ]
        inputs = dict(**dict(zip(argnames, args)), **kwargs)
        output = self(*args, **kwargs)

        # get input params expression
        input_params = [
            inputs[name].as_sql_parameters(name) for name in self.tableparams
        ]
        input_params = ", ".join(input_params)

        # get return statement
        if type(output) == Table:
            output_expr = output.as_sql_return_declaration(self.return_name)
            return_stmt = self._returntemplate.substitute(
                dict(return_name=self.return_name)
            )
        else:
            output_expr = SQLTYPES[type(output)]
            return_stmt = f"return {self.return_name}\n"

        # gen code for ArrayBundle definitions
        table_defs = []
        stop = 0
        for name in self.tableparams:
            table = inputs[name]
            start, stop = stop, stop + table.shape[1]
            table_defs += [f"{name} = ArrayBundle(___columns[{start}:{stop}])"]
        table_defs = "\n".join(table_defs)

        # gen code for loopback params
        loopback_calls = []
        for name in self.loopbackparams:
            lpb = inputs[name]
            loopback_calls += [f'{name} = _conn.execute("SELECT * FROM {lpb.name}")']
        loopback_calls = "\n".join(loopback_calls)

        # gen code for literal parameters
        literal_defs = []
        for name in self.literalparams:
            ltr = inputs[name]
            literal_defs += [f"{name} = {ltr.value}"]
        literal_defs = "\n".join(literal_defs)

        # output udf code
        prfx = " " * 4
        subs = dict(
            func_name=self.name,
            input_params=input_params,
            output_expr=output_expr,
            table_defs=indent(table_defs, prfx),
            loopbacks=indent(loopback_calls, prfx),
            literals=indent(literal_defs, prfx),
            body=indent(self.body, prfx),
            return_stmt=indent(return_stmt, prfx),
        )
        return self._udftemplate.substitute(subs)


def monet_udf(func):
    global UDF_REGISTER

    verify_annotations(func)

    ugen = UDFGenerator(func)
    UDF_REGISTER[ugen.name] = ugen
    return ugen


def verify_annotations(func):
    allowed_types = (Table, LiteralParameter, LoopbackTable)
    sig = inspect.signature(func)
    argnames = sig.parameters.keys()
    annotations = func.__annotations__
    if any(annotations.get(arg, None) not in allowed_types for arg in argnames):
        raise TypeError("Function is not properly annotated as a Monet UDF")


def generate_udf(udf_name, table_schema, table_rows, literalparams):
    gen = UDF_REGISTER[udf_name]

    ncols = len(table_schema)
    dtype = table_schema[0]["type"]
    if not all(col["type"] == dtype for col in table_schema):
        raise TypeError("Can't have different types in columns yet")
    table = Table(dtype, shape=(table_rows, ncols))

    literals = [LiteralParameter(literalparams[name]) for name in gen.literalparams]
    return UDF_REGISTER[udf_name].to_sql(table, *literals)


# -------------------------------------------------------- #
# Examples                                                 #
# -------------------------------------------------------- #
@monet_udf
def f(x: Table, y: Table, z: Table, p: LiteralParameter, r: LiteralParameter):
    result = len(x)
    return result


x = Table(dtype=int, shape=(100, 10))
y = Table(dtype=float, shape=(100, 2))
z = Table(dtype=float, shape=(100, 5))
# f(x, y, z=z)
print(f.to_sql(x, y, z, p=LiteralParameter(5), r=LiteralParameter([0.8, 0.95])))


@monet_udf
def compute_gramian(data: Table, coeffs: LoopbackTable, pp: LiteralParameter):
    gramian = coeffs.T @ data.T @ data
    return gramian


print(
    compute_gramian(
        Table(dtype=int, shape=(100, 10)),
        LoopbackTable("coeffs", dtype=float, shape=(10,)),
        LiteralParameter(5),
    )
)
print(
    compute_gramian.to_sql(
        Table(dtype=int, shape=(100, 10)),
        LoopbackTable("coeffs", dtype=float, shape=(10,)),
        LiteralParameter(5),
    )
)


@monet_udf
def half_table(table: Table):
    ncols = table.shape[1]
    if ncols >= 2:
        result = table[:, 0 : (ncols // 2)]
    else:
        result = table
    return result


half_table(Table(dtype=float, shape=(50, 12)))


@monet_udf
def ret_one(data: Table):
    result = 1
    return result


ret_one(Table(dtype=int, shape=(1,)))


tname = "compute_gramian"
table_schema = [
    {"name": "asdkjg", "type": int},
    {"name": "weori", "type": int},
    {"name": "oihdf", "type": int},
]
nrows = 1234
# print(generate_udf(tname, table_schema, nrows, {"pp": 5}))
