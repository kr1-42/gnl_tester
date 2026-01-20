#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_FILES = ["get_next_line.c", "get_next_line_utils.c"]
PROJECT_HEADERS = ["get_next_line.h"]


MAIN_C = r"""
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include "get_next_line.h"

int main(int argc, char **argv)
{
    int fd;
    char *line;

    if (argc != 2)
    {
        const char msg[] = "usage: ./gnl_test <file>\n";
        write(2, msg, sizeof(msg) - 1);
        return 2;
    }
    fd = open(argv[1], O_RDONLY);
    if (fd < 0)
    {
        perror("open");
        return 1;
    }
    while ((line = get_next_line(fd)) != NULL)
    {
        write(1, line, ft_strlen(line));
        free(line);
    }
    close(fd);
    return 0;
}
"""


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def compile_runner(build_dir: Path, buffer_size: int) -> Path:
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
        str(Path.cwd()),
        *[str(Path.cwd() / f) for f in PROJECT_FILES],
        str(main_c),
        "-o",
        str(output_bin),
    ]
    result = run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return output_bin


def expected_output(content: str) -> str:
    return content


def build_test_cases(tmp_dir: Path):
    cases = []

    def add_case(name: str, content: str):
        path = tmp_dir / name
        path.write_text(content)
        cases.append((name, path, content))

    add_case("empty.txt", "")
    add_case("single_line_no_nl.txt", "hello")
    add_case("single_line_with_nl.txt", "hello\n")
    add_case("two_lines.txt", "hello\nworld\n")
    add_case("mixed_end.txt", "hello\nworld")
    add_case("only_newlines.txt", "\n\n\n")
    add_case("spaces_tabs.txt", "\t  abc  \n\tdef\n")
    add_case("long_line.txt", "x" * 5000 + "\n")
    add_case("long_no_nl.txt", "y" * 5000)
    add_case("many_lines.txt", "".join(f"line {i}\n" for i in range(200)))
    return cases


def main():
    root = Path(__file__).resolve().parent
    os.chdir(root)

    missing = [f for f in PROJECT_FILES + PROJECT_HEADERS if not (root / f).exists()]
    if missing:
        print(f"Missing source files: {', '.join(missing)}")
        return 2

    buffer_sizes = [1, 2, 3, 4, 5, 7, 8, 16, 32, 64, 128, 100000]
    ok = True

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cases = build_test_cases(tmp_dir)

        for bs in buffer_sizes:
            try:
                runner = compile_runner(tmp_dir, bs)
            except RuntimeError as exc:
                print(f"[BUFFER_SIZE={bs}] compile error:\n{exc}")
                ok = False
                continue

            for name, path, content in cases:
                result = run([str(runner), str(path)])
                if result.returncode != 0:
                    print(f"[BUFFER_SIZE={bs}] {name}: runtime error:\n{result.stderr.strip()}")
                    ok = False
                    continue

                out = result.stdout
                exp = expected_output(content)
                if out != exp:
                    print(f"[BUFFER_SIZE={bs}] {name}: mismatch")
                    print(f"Expected length: {len(exp)} | Got length: {len(out)}")
                    ok = False

    if ok:
        print("All tests passed.")
        return 0
    print("Some tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
