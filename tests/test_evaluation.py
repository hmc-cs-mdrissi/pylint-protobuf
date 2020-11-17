import astroid
import pytest

from pylint_protobuf.evaluation import (
    assign,
    assignattr,
    resolve,
    evaluate,
    Scope,
)
from pylint_protobuf.parse_pb2 import Module, TypeClass


def test_resolve_name():
    Person = object()
    scope = {'Person': Person}
    node = astroid.extract_node('Person')
    assert resolve(scope, node) is Person

def test_resolve_constant_slice():
    Person = object()
    scope = {'Person': Person}
    node = astroid.extract_node('[Person][0]')
    assert resolve(scope, node) is Person

def test_resolve_constant_dict():
    Person = object()
    scope = {'Person': Person}
    node = astroid.extract_node('{"a": Person}["a"]')
    assert resolve(scope, node) is Person

def test_resolve_nested_dict():
    Person = object()
    scope = {'Person': Person}
    node = astroid.extract_node("""
    {
        "outer": {
            "inner": Person
        }
    }["outer"]["inner"]
    """)
    assert resolve(scope, node) is Person

@pytest.mark.skip(reason='changes in typeof')
def test_resolve_call():
    Person = object()
    scope = {'Person': TypeClass(Person)}
    node = astroid.extract_node('Person()')
    assert resolve(scope, node) is Person

@pytest.mark.skip(reason='changes in typeof')
def test_resolve_import():
    Person = TypeClass(object())
    mod_globals = {'module_pb2.Person': Person}
    module_pb2 = Module('module_pb2', mod_globals)
    scope = {'module_pb2': module_pb2}
    node = astroid.extract_node('module_pb2.Person')
    assert resolve(scope, node) is Person

def test_scope_assign():
    scope = Scope({'x': 123})
    assert scope['x'] == 123
    scope.assign('x', 456)
    assert scope['x'] == 456

def test_scope_push():
    scope = Scope({'x': 123})
    scope.push()
    assert scope['x'] == 123

def test_scope_push_shadows():
    scope = Scope({'x': 123})
    scope.push({'x': 456})
    assert scope['x'] == 456
    scope.pop()
    assert scope['x'] == 123

def evaluate_str(scope, expr_str):
    return evaluate(scope, astroid.extract_node(expr_str))

def test_evaluate_name():
    scope = Scope({'x': 123})
    assert evaluate_str(scope, 'x') == 123

def test_evaluate_constant():
    scope = Scope({'x': 123})
    assert evaluate_str(scope, '456') == 456

def test_evaluate_attribute():
    class Obj(object):
        attr = 'attribute'
    scope = Scope({'name': Obj()})
    assert evaluate_str(scope, 'name.attr') == 'attribute'

def test_evaluate_attributeerror():
    class Obj(object):
        attr = 'attribute'
    scope = Scope({'name': Obj()})
    with pytest.raises(AttributeError):
        evaluate_str(scope, 'name.missing')  # Would rather it didn't raise

def test_evaluate_recursive_attributes():
    class Inner(object):
        attr = 'recursive_attribute'
    class Outer(object):
        inner = Inner()
    scope = Scope({'outer': Outer()})
    assert evaluate_str(scope, 'outer.inner.attr') == 'recursive_attribute'

def test_evaluate_recursive_attributeerror():
    class Inner(object):
        attr = 'recursive_attribute'
    class Outer(object):
        inner = Inner()
    scope = Scope({'outer': Outer()})
    with pytest.raises(AttributeError):
        evaluate_str(scope, 'outer.missing.attr')  # Would rather it didn't raise

def test_evaluate_recursive_top_attributeerror():
    class Obj(object):
        attr = 'one-two-three'
    scope = Scope({'name': Obj()})
    with pytest.raises(KeyError):
        evaluate_str(scope, 'missing.attr')  # Would rather it didn't raise

def assign_str(scope, expr_str):
    assign_node = astroid.extract_node(expr_str)
    assert isinstance(assign_node, astroid.Assign)
    lhs, rhs = assign_node.targets[0], assign_node.value
    return assign(scope, lhs, rhs)

def test_assign_renaming():
    scope = Scope({'x': 123})
    assert evaluate_str(scope, 'x') == 123
    assign_str(scope, 'x = 456')
    assert evaluate_str(scope, 'x') == 456

def assignattr_str(scope, expr_str):
    assign_node = astroid.extract_node(expr_str)
    assert isinstance(assign_node, astroid.Assign)
    lhs, rhs = assign_node.targets[0], assign_node.value
    return assignattr(scope, lhs, rhs)

def test_assignattr_renaming():
    class Obj(object):
        attr = 'red'
    scope = Scope({'obj': Obj()})
    assert evaluate_str(scope, 'obj.attr') == 'red'
    assignattr_str(scope, 'obj.attr = "blue"')
    assert evaluate_str(scope, 'obj.attr') == 'blue'

def test_assignattr_recursive_attributes():
    class Inner(object):
        attr = 'red'
    class Outer(object):
        inner = Inner()
    scope = Scope({'outer': Outer()})
    assignattr_str(scope, 'outer.inner.attr = "blue"')
    assert evaluate_str(scope, 'outer.inner.attr') == 'blue'

def test_assignattr_swap_out_object():
    class Inner(object):
        attr = 'red'
    class Outer(object):
        inner = Inner()
    scope = Scope({'outer': Outer()})
    assignattr_str(scope, 'outer.inner = "seeya"')
    with pytest.raises(AttributeError):
        evaluate_str(scope, 'outer.inner.attr')
    assert evaluate_str(scope, 'outer.inner') == 'seeya'
