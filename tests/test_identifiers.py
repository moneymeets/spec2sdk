from spec2sdk.models.identifiers import make_class_name, make_constant_name, make_identifier, make_variable_name


def test_remove_invalid_leading_characters():
    assert make_identifier("12+34-_56Variable78Name90") == "Variable78Name90"


def test_replace_invalid_characters():
    assert make_identifier("Variable12%#&34(@!56Name78*-,") == "Variable12_34_56Name78"


def test_python_keywords():
    assert make_identifier("def") == "def_"


def test_make_class_name():
    assert make_class_name("issue:comment") == "IssueComment"


def test_make_constant_name():
    assert make_constant_name("family_status") == "FAMILY_STATUS"


def test_make_variable_name():
    assert make_variable_name("UserID") == "user_id"
