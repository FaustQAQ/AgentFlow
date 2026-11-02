import pytest

from app.services.execution_context import ExecutionContext


def test_saves_and_reads_step_output() -> None:
    context = ExecutionContext()
    output = {"current_sales": 120.0}

    context.save_step_output(1, output)

    assert context.get_step_output(1) == output


def test_reads_field_from_step_output() -> None:
    context = ExecutionContext()
    context.save_step_output(1, {"current_sales": 120.0})

    assert context.get_step_field(1, "current_sales") == 120.0


def test_missing_step_raises_clear_key_error() -> None:
    with pytest.raises(KeyError, match="No output found for step 1"):
        ExecutionContext().get_step_output(1)


def test_missing_field_raises_clear_key_error() -> None:
    context = ExecutionContext()
    context.save_step_output(1, {"current_sales": 120.0})

    with pytest.raises(KeyError, match="Field 'growth_rate' not found"):
        context.get_step_field(1, "growth_rate")


def test_returned_output_cannot_modify_internal_context() -> None:
    context = ExecutionContext()
    context.save_step_output(1, {"metrics": {"growth_rate": 20.0}})

    output = context.get_step_output(1)
    output["metrics"]["growth_rate"] = 999.0

    assert context.get_step_field(1, "metrics") == {"growth_rate": 20.0}


def test_resolves_nested_dict_and_list_references() -> None:
    context = ExecutionContext()
    context.save_step_output(1, {"value": 7})

    resolved = context.resolve_references(
        {"payload": {"amount": "$steps.1.value"}, "values": ["$steps.1.value", 2]}
    )

    assert resolved == {"payload": {"amount": 7}, "values": [7, 2]}


def test_plain_values_remain_unchanged() -> None:
    context = ExecutionContext()

    value = {"text": "steps are ordinary text", "count": 2, "enabled": True, "empty": None}

    assert context.resolve_references(value) == value


def test_invalid_reference_format_raises_clear_value_error() -> None:
    with pytest.raises(ValueError, match=r"expected \$steps.<step_index>.<field>"):
        ExecutionContext().resolve_references("$steps.invalid.value")
