import io

from optimizer.term import BOLD, GREEN, RED, RESET, Console


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_color_resolution(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    assert Console(stream=io.StringIO()).color is False
    assert Console(stream=Tty()).color is True
    assert Console(stream=Tty(), color=False).color is False
    assert Console(stream=io.StringIO(), color=True).color is True

    monkeypatch.setenv("NO_COLOR", "1")
    assert Console(stream=Tty()).color is False
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert Console(stream=Tty()).color is False


def test_paint_and_print():
    plain = Console(stream=io.StringIO(), color=False)
    assert plain.paint("x", BOLD) == "x"
    plain.print("hello", BOLD)
    assert plain.stream.getvalue() == "hello\n"

    colored = Console(stream=io.StringIO(), color=True)
    assert colored.paint("x", BOLD, RED) == f"{BOLD}{RED}x{RESET}"
    colored.print("hi")
    assert colored.stream.getvalue() == "hi\n"


def test_diff_and_candidate_painting():
    c = Console(stream=io.StringIO(), color=True)
    c.diff("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n ctx\n")
    out = c.stream.getvalue().split("\n")
    assert out[0] == f"{BOLD}--- a/x.py{RESET}"
    assert out[2].startswith("\x1b[36m@@")
    assert out[3] == f"{RED}-old{RESET}"
    assert out[4] == f"{GREEN}+new{RESET}"
    assert out[5] == " ctx"

    c = Console(stream=io.StringIO(), color=True)
    c.candidate("Candidate A\nResult: VALID")
    assert c.stream.getvalue() == f"Candidate A\n{GREEN}Result: VALID{RESET}\n"
    c = Console(stream=io.StringIO(), color=True)
    c.candidate("Result: REJECTED (slower)")
    assert c.stream.getvalue() == f"{RED}Result: REJECTED (slower){RESET}\n"
