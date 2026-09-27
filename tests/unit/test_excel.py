"""Excel tools, against a fake COM object graph so they run without Excel installed.

The live behaviour is covered by a manual test; these lock in the logic that bit hardest:
late-bound Address, indexed collection access, sort verification and the backup.
"""
from pathlib import Path

import pytest

import app.tools.excel as excel
from app.tools.excel import ExcelError, _address, _free_name, excel_tools


class FakeRange:
    def __init__(self, address="A1:D6", rows=6, columns=4, late_bound=True):
        self._address = address
        self.Rows = FakeCount(rows)
        self.Columns = FakeCount(columns)
        self.Row = 1
        self.Value = None
        self.Formula = None
        self.fitted = False
        self._late = late_bound

    @property
    def Address(self):
        return self._address if self._late else (lambda a, b: self._address)

    def Cells(self, row=1, col=1):
        cell = FakeRange(f"R{row}C{col}")
        cell.Value = f"v{row}{col}"
        return cell

    def AutoFit(self):
        self.fitted = True


class FakeCount:
    def __init__(self, count):
        self.Count = count

    def __call__(self, *_):
        return FakeRange()

    def AutoFit(self):
        pass


def test_address_works_late_bound_and_early_bound():
    assert _address(FakeRange("$A$1:$D$6", late_bound=True)) == "A1:D6"
    assert _address(FakeRange("$A$1:$D$6", late_bound=True), absolute=True) == "$A$1:$D$6"
    assert _address(FakeRange("A1:D6", late_bound=False)) == "A1:D6"


def test_free_name_avoids_clashes():
    class Book:
        def __init__(self, names):
            self._names = names
            self.Worksheets = type("W", (), {"Count": len(names),
                                             "__call__": lambda s, i: type("S", (), {"Name": names[i - 1]})()})()

    assert _free_name(Book(["Data"]), "Pivot") == "Pivot"
    assert _free_name(Book(["Data", "Pivot"]), "Pivot") == "Pivot2"
    assert _free_name(Book(["Data", "Pivot", "Pivot2"]), "Pivot") == "Pivot3"


def test_every_tool_reports_a_clear_error_when_excel_is_not_there(monkeypatch, tmp_path):
    """No Excel must never look like success, and the message must say what to do."""
    monkeypatch.setattr(excel, "_APP", None)
    monkeypatch.setattr(excel, "_app", lambda create=False: (_ for _ in ()).throw(ExcelError(excel.NOT_OPEN)))
    tools = {t.name: t for t in excel_tools(tmp_path, lambda p: Path(p))}

    for name, args in [("excel_sheet_info", {}), ("excel_read", {"range": "A1"}),
                       ("excel_autofit", {"columns": "A"}),
                       ("excel_write", {"range": "A1", "values": "x"}),
                       ("excel_sort", {"column": "A"}),
                       ("excel_pivot_table", {"rows": "R", "values": "V"}),
                       ("excel_calculate", {"formula": "SUM(A:A)"}),
                       ("excel_find", {"text": "x"}),
                       ("excel_compare", {"left": "A", "right": "B"}),
                       ("excel_filter", {"column": "A", "contains": "x"}),
                       ("excel_edit_rows", {"action": "insert", "at": 2}),
                       ("excel_format", {"bold": True}),
                       ("excel_chart", {"labels": "A", "values": "B"}),
                       ("excel_save", {})]:
        result = tools[name].run(**args)
        assert not result.ok, name
        assert "open" in result.error.lower(), (name, result.error)


def test_open_refuses_a_file_that_is_not_there(tmp_path):
    tools = {t.name: t for t in excel_tools(tmp_path, lambda p: Path(p))}
    result = tools["excel_open"].run(path=str(tmp_path / "nope.xlsx"))
    assert not result.ok and "no file" in result.error.lower()


def test_sort_reports_failure_when_the_sheet_did_not_change(monkeypatch, tmp_path):
    """Excel accepts a bad sort key and silently does nothing; that must not read as success."""
    class Sheet:
        Name = "Data"

        def __init__(self):
            self.Sort = type("S", (), {"SortFields": type("F", (), {"Clear": lambda s: None,
                                                                    "Add": lambda s, **k: None})(),
                                       "SetRange": lambda s, r: None, "Apply": lambda s: None,
                                       "Header": 0, "MatchCase": False})()
            self.UsedRange = FakeRange()

        def Range(self, *a):
            return FakeRange()

        def Columns(self, letter):
            return FakeCount(1)

    class Book:
        Name = "Book1.xlsx"
        FullName = "C:/x/Book1.xlsx"
        Path = "C:/x"

        def __init__(self):
            self.ActiveSheet = Sheet()
            self.Worksheets = type("W", (), {"Count": 1, "__call__": lambda s, i: Sheet()})()

        def SaveCopyAs(self, target):
            Path(target).write_text("backup")

    class App:
        DisplayAlerts = True
        ActiveWorkbook = Book()
        Workbooks = type("WB", (), {"Count": 1, "__call__": lambda s, i: Book()})()

    monkeypatch.setattr(excel, "_app", lambda create=False: App())
    tools = {t.name: t for t in excel_tools(tmp_path, lambda p: Path(p))}
    result = tools["excel_sort"].run(column="D", descending=True)
    assert not result.ok
    assert "didn't sort" in result.error


def test_the_tool_set_is_what_the_prompt_promises(tmp_path):
    names = {t.name for t in excel_tools(tmp_path, lambda p: Path(p))}
    assert names == {"excel_open", "excel_sheet_info", "excel_read", "excel_autofit",
                     "excel_write", "excel_sort", "excel_pivot_table", "excel_save",
                     "excel_calculate", "excel_find", "excel_compare",
                     "excel_filter", "excel_edit_rows", "excel_format", "excel_chart"}


def test_sort_does_not_shadow_the_builtin_range(tmp_path):
    """A parameter called `range` once broke sorting with \"'str' object is not callable\"."""
    import inspect

    tool = next(t for t in excel_tools(tmp_path, lambda p: Path(p)) if t.name == "excel_sort")
    assert "range" not in tool.parameters["properties"], "use data_range, not range"


def test_column_letters_are_right():
    from app.tools.excel import _column_letter

    assert [_column_letter(n) for n in (1, 2, 26, 27, 28, 52, 53)] ==         ["A", "B", "Z", "AA", "AB", "AZ", "BA"]


def test_column_letters_and_indexes_are_inverses():
    from app.tools.excel import _column_index, _column_letter

    for n in (1, 2, 26, 27, 28, 52, 53, 702, 703):
        assert _column_index(_column_letter(n)) == n


def test_formatting_only_the_header_freeze_needs_no_range(monkeypatch, tmp_path):
    """"Freeze the header row" on its own used to crash: `range` had no default."""
    import app.tools.excel as excel

    monkeypatch.setattr(excel, "_APP", None)
    monkeypatch.setattr(excel, "_app", lambda create=False: (_ for _ in ()).throw(ExcelError(excel.NOT_OPEN)))
    tools = {t.name: t for t in excel.excel_tools(tmp_path, lambda p: Path(p))}
    assert tools["excel_format"].parameters.get("required") in (None, [])

    result = tools["excel_format"].run(freeze_header=True)
    assert not result.ok
    assert "open" in result.error.lower(), f"must fail on Excel, not on arguments: {result.error}"


def test_deleting_rows_asks_first_but_inserting_does_not(tmp_path):
    from app.tools.base import Risk
    from app.tools.excel import excel_tools

    tool = next(t for t in excel_tools(tmp_path, lambda p: Path(p)) if t.name == "excel_edit_rows")
    assert tool.risk_for({"action": "delete", "at": 2}) is Risk.MEDIUM
    assert tool.confirm_question(action="delete", at=2, count=3, what="row")
    assert tool.confirm_question(action="insert", at=2) is None
