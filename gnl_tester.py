#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
from pathlib import Path


GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


PROJECT_FILES = ["get_next_line.c", "get_next_line_utils.c"]
PROJECT_HEADERS = ["get_next_line.h"]


MAIN_C = r"""
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include "get_next_line.h"

int main(int argc, char **argv)
{
    int fd;
    char *line;
    int should_close = 1;

    if (argc != 2)
    {
        const char msg[] = "usage: ./gnl_test <file|stdin>\n";
        write(2, msg, sizeof(msg) - 1);
        return 2;
    }
    if (strcmp(argv[1], "stdin") == 0 || strcmp(argv[1], "0") == 0)
    {
        fd = 0;
        should_close = 0;
    }
    else
    {
        fd = open(argv[1], O_RDONLY);
        if (fd < 0)
        {
            perror("open");
            return 1;
        }
    }
    while ((line = get_next_line(fd)) != NULL)
    {
        write(1, line, ft_strlen(line));
        free(line);
    }
    if (should_close)
        close(fd);
    return 0;
}
"""


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def compile_runner(build_dir: Path, project_root: Path, buffer_size: int) -> Path:
    main_c = build_dir / "gnl_test_main.c"
    main_c.write_text(MAIN_C)

    output_bin = build_dir / "gnl_test"
    cmd = [
        "gcc",
        "-Wall",
        "-Wextra",
        "-Werror",
        f"-D", f"BUFFER_SIZE={buffer_size}",
        "-I",
        str(project_root),
        *[str(project_root / f) for f in PROJECT_FILES],
        str(main_c),
        "-o",
        str(output_bin),
    ]
    result = run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return output_bin


def expected_output(content: str, normalize_crlf: bool) -> str:
    if normalize_crlf:
        return content.replace("\r\n", "\n")
    return content


def build_test_cases(tmp_dir: Path):
    cases = []

    def add_case(name: str, content: str, normalize_crlf: bool = False):
        path = tmp_dir / name
        path.write_text(content)
        cases.append((name, path, content, normalize_crlf))

    add_case("empty.txt", "")
    add_case("single_line_no_nl.txt", "hello")
    add_case("single_line_with_nl.txt", "hello\n")
    add_case("two_lines.txt", "hello\nworld\n")
    add_case("mixed_end.txt", "hello\nworld")
    add_case("only_newlines.txt", "\n\n\n")
    add_case("spaces_tabs.txt", "\t  abc  \n\tdef\n")
    add_case("leading_newline.txt", "\nabc\n")
    add_case("trailing_newlines.txt", "abc\n\n\n")
    add_case("no_trailing_newline_many.txt", "a\n\n\nb")
    add_case("crlf_lines.txt", "a\r\n\r\nb\r\n", normalize_crlf=True)
    add_case("mixed_lengths.txt", "short\n" + "m" * 100 + "\n" + "n" * 4096 + "\nend")
    add_case("many_small_lines.txt", "\n".join("x" for _ in range(500)) + "\n")
    add_case("long_line.txt", "x" * 5000 + "\n")
    add_case("long_no_nl.txt", "y" * 5000)
    add_case("many_lines.txt", "".join(f"line {i}\n" for i in range(200)))
    return cases


def build_stdin_test_cases():
    stdin_cases = []
    stdin_cases.append(("stdin_empty", ""))
    stdin_cases.append(("stdin_single_line", "hello from stdin\n"))
    stdin_cases.append(("stdin_multiple_lines", "line1\nline2\nline3\n"))
    stdin_cases.append(("stdin_no_newline", "no newline at end"))
    stdin_cases.append(("stdin_long_line", "x" * 5000 + "\n"))
    return stdin_cases


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    os.chdir(project_root)

    missing = [f for f in PROJECT_FILES + PROJECT_HEADERS if not (project_root / f).exists()]
    if missing:
        print(f"Missing source files: {', '.join(missing)}")
        return 2

    buffer_sizes = [1, 2, 3, 4, 5, 7, 8, 16, 32, 64, 128, 1024, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304, 8388608]
    ok = True

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cases = build_test_cases(tmp_dir)
        stdin_cases = build_stdin_test_cases()

        for bs in buffer_sizes:
            try:
                runner = compile_runner(tmp_dir, project_root, bs)
            except RuntimeError as exc:
                print(f"{RED}[Ko ]{RESET} [BUFFER_SIZE={bs}] compile error")
                print(exc)
                ok = False
                continue

            for name, path, content, normalize_crlf in cases:
                result = run([str(runner), str(path)])
                if result.returncode != 0:
                    print(f"{RED}[Ko ]{RESET} [BUFFER_SIZE={bs}] {name}: runtime error")
                    if result.stderr.strip():
                        print(result.stderr.strip())
                    ok = False
                    continue

                out = result.stdout
                exp = expected_output(content, normalize_crlf)
                actual = out.replace("\r\n", "\n") if normalize_crlf else out
                if actual != exp:
                    print(f"{RED}[Ko ]{RESET} [BUFFER_SIZE={bs}] {name}: mismatch")
                    print(f"Expected length: {len(exp)} | Got length: {len(out)}")
                    ok = False
                else:
                    print(f"{GREEN}[Ok]{RESET} [BUFFER_SIZE={bs}] {name}")

            # Test stdin (fd 0)
            for name, content in stdin_cases:
                result = subprocess.run(
                    [str(runner), "stdin"],
                    input=content,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    print(f"{RED}[Ko ]{RESET} [BUFFER_SIZE={bs}] {name}: runtime error")
                    if result.stderr.strip():
                        print(result.stderr.strip())
                    ok = False
                    continue

                if result.stdout != content:
                    print(f"{RED}[Ko ]{RESET} [BUFFER_SIZE={bs}] {name}: mismatch")
                    print(f"Expected length: {len(content)} | Got length: {len(result.stdout)}")
                    ok = False
                else:
                    print(f"{GREEN}[Ok]{RESET} [BUFFER_SIZE={bs}] {name}")

    if ok:
        print("All tests passed.")
        return 0
    print("Some tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
