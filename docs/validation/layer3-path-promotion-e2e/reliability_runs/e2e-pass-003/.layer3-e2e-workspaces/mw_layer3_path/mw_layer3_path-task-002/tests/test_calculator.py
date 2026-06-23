from sample_project.calculator import safe_divide


def test_safe_divide_handles_zero():
    assert safe_divide(5, 0) is None


def test_safe_divide_regular_case():
    assert safe_divide(8, 2) == 4
