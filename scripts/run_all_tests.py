#!/usr/bin/env python3
"""Run repository checks, Python smoke tests, and available HDL simulations.

Only Python's standard library is required by this runner itself.  When
Icarus Verilog is unavailable, HDL cases are reported as SKIP and the overall
summary is INCOMPLETE rather than PASS.  A real command or testbench failure
always produces a non-zero process exit status.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPT_DIR.parent
PASS_OUTPUT = re.compile(r"(?im)(?:\[PASS\]|\bPASS\b)")
FAIL_OUTPUT = re.compile(r"(?im)^\s*(?:\[FAIL\]|FATAL(?:\s|:)|ERROR(?:\s|:))")


@dataclass(frozen=True)
class TestResult:
    name: str
    status: str
    detail: str
    duration: float = 0.0
    command: str = ""
    output: str = ""


@dataclass(frozen=True)
class Simulator:
    iverilog: Path | None
    vvp: Path | None
    ivl_base: Path | None
    vvp_module_dir: Path | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.error is None and self.iverilog is not None and self.vvp is not None


@dataclass(frozen=True)
class HDLCase:
    name: str
    working_directory: Path
    file_list: Path
    compiler_arguments: tuple[str, ...] = ()


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (LookupError, OSError):
                pass


def command_text(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def output_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "completed with no output"
    for line in reversed(lines):
        if PASS_OUTPUT.search(line):
            return line
    return lines[-1]


def run_command(
    name: str,
    command: Sequence[str],
    cwd: Path,
    timeout: float,
    *,
    require_pass_text: bool = False,
) -> TestResult:
    started = time.monotonic()
    display = command_text(command)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return TestResult(
            name,
            "FAIL",
            f"timed out after {timeout:g} seconds",
            time.monotonic() - started,
            display,
            output,
        )
    except OSError as exc:
        return TestResult(
            name,
            "FAIL",
            f"could not start command: {exc}",
            time.monotonic() - started,
            display,
        )

    duration = time.monotonic() - started
    output = completed.stdout or ""
    if completed.returncode != 0:
        return TestResult(
            name,
            "FAIL",
            f"exit code {completed.returncode}",
            duration,
            display,
            output,
        )
    if require_pass_text and FAIL_OUTPUT.search(output):
        return TestResult(
            name,
            "FAIL",
            "testbench emitted an explicit failure marker",
            duration,
            display,
            output,
        )
    if require_pass_text and not PASS_OUTPUT.search(output):
        return TestResult(
            name,
            "FAIL",
            "command returned 0 but emitted no PASS marker",
            duration,
            display,
            output,
        )
    return TestResult(
        name,
        "PASS",
        output_summary(output),
        duration,
        display,
        output,
    )


def executable_names(name: str) -> tuple[str, ...]:
    return (name, f"{name}.exe") if os.name == "nt" else (name, f"{name}.exe")


def local_executable_candidates(root: Path, name: str) -> list[Path]:
    names = executable_names(name)
    candidates: list[Path] = []
    local_roots = (
        root / "tools" / "iverilog",
        root / ".tools" / "iverilog",
        root / "toolchain" / "iverilog",
        root / "tools",
        root / ".tools",
    )
    for local_root in local_roots:
        for executable in names:
            candidates.extend((local_root / "bin" / executable, local_root / executable))

    # A one-directory-deep scan supports an unpacked temporary toolchain while
    # avoiding an expensive recursive search through the whole temporary tree.
    temp_roots = [Path(tempfile.gettempdir())]
    # WSL can inherit Windows' TMP/TEMP, making tempfile.gettempdir() point to
    # /mnt/c/... even though locally unpacked Linux tools live under /tmp.
    posix_tmp = Path("/tmp")
    if posix_tmp.is_dir() and posix_tmp not in temp_roots:
        temp_roots.append(posix_tmp)
    for temp_root in temp_roots:
        for executable in names:
            candidates.extend(temp_root.glob(f"*/bin/{executable}"))
            candidates.extend(temp_root.glob(f"*/usr/bin/{executable}"))
            candidates.append(temp_root / executable)
    return candidates


def resolve_executable(requested: str | None, env_name: str, root: Path, name: str) -> Path | None:
    values = [requested, os.environ.get(env_name)]
    for value in values:
        if not value:
            continue
        expanded = Path(value).expanduser()
        if expanded.is_file():
            return expanded.resolve()
        found = shutil.which(value)
        if found:
            return Path(found).resolve()
        # Explicit values are validated later so a typo is a failure, not a
        # misleading automatic SKIP.
        if value == requested:
            return expanded.resolve()

    found = shutil.which(name)
    if found:
        return Path(found).resolve()
    for candidate in local_executable_candidates(root, name):
        if candidate.is_file():
            return candidate.resolve()
    return None


def derived_ivl_directories(iverilog: Path | None) -> list[Path]:
    if iverilog is None:
        return []
    bin_dir = iverilog.parent
    prefix = bin_dir.parent if bin_dir.name.casefold() == "bin" else bin_dir
    candidates = [bin_dir / "ivl", prefix / "lib" / "ivl", prefix / "lib64" / "ivl"]
    for lib_root in (prefix / "lib", prefix / "lib64"):
        if lib_root.is_dir():
            candidates.extend(sorted(lib_root.glob("*/ivl")))
    return candidates


def valid_ivl_base(path: Path) -> bool:
    return path.is_dir() and any((path / name).is_file() for name in ("ivl", "ivl.exe"))


def valid_vvp_module_dir(path: Path) -> bool:
    return path.is_dir() and any(path.glob("*.vpi"))


def resolve_directory(
    explicit: str | None,
    env_name: str,
    candidates: Sequence[Path],
    validator,
) -> tuple[Path | None, str | None]:
    requested = explicit or os.environ.get(env_name)
    if requested:
        path = Path(requested).expanduser().resolve()
        if not validator(path):
            return None, f"{env_name} directory is invalid: {path}"
        return path, None
    for candidate in candidates:
        if validator(candidate):
            return candidate.resolve(), None
    return None, None


def detect_simulator(args: argparse.Namespace, root: Path) -> Simulator:
    iverilog = resolve_executable(args.iverilog, "IVERILOG", root, "iverilog")
    vvp = resolve_executable(args.vvp, "VVP", root, "vvp")
    errors: list[str] = []
    if args.iverilog and (iverilog is None or not iverilog.is_file()):
        errors.append(f"iverilog executable is invalid: {iverilog}")
    if args.vvp and (vvp is None or not vvp.is_file()):
        errors.append(f"vvp executable is invalid: {vvp}")

    candidates = derived_ivl_directories(iverilog)
    ivl_base, base_error = resolve_directory(
        args.iverilog_base,
        "IVERILOG_BASE",
        candidates,
        valid_ivl_base,
    )
    vvp_module_dir, module_error = resolve_directory(
        args.vvp_module_dir,
        "VVP_MODULE_PATH",
        candidates,
        valid_vvp_module_dir,
    )
    if base_error:
        errors.append(base_error)
    if module_error:
        errors.append(module_error)
    return Simulator(iverilog, vvp, ivl_base, vvp_module_dir, "; ".join(errors) or None)


def hdl_cases(root: Path) -> list[HDLCase]:
    warmup_root = root / "labs" / "Lab01_W1_W2" / "warmups"
    cases = [
        HDLCase("Warmup 01 parameterized adder", warmup_root / "01_parameterized_adder" / "solution", warmup_root / "01_parameterized_adder" / "solution" / "files.f"),
        HDLCase("Warmup 02 valid/ready MAC", warmup_root / "02_valid_ready_mac" / "solution", warmup_root / "02_valid_ready_mac" / "solution" / "files.f"),
        HDLCase("Warmup 03 synchronous FIFO", warmup_root / "03_sync_fifo" / "solution", warmup_root / "03_sync_fifo" / "solution" / "files.f"),
        HDLCase("Warmup 04 testbench basics", warmup_root / "04_testbench_basics" / "solution", warmup_root / "04_testbench_basics" / "solution" / "files.f"),
    ]
    board_demo = root / "labs" / "Lab01_W1_W2" / "board_demo"
    cases.append(
        HDLCase(
            "Lab01 PYNQ-Z2 switch/LED board demo",
            board_demo / "sim",
            board_demo / "sim" / "files.f",
            ("-Wall", "-s", "tb_pynq_z2_adder_demo"),
        )
    )
    for lab_name, label in (
        ("Lab02_W3_W4", "Lab02 dense PE"),
        ("Lab03_W5_W6", "Lab03 sparse array"),
        ("Lab04_W7_W8", "Lab04 AXI stream accelerator"),
    ):
        lab = root / "labs" / lab_name
        cases.append(HDLCase(label, lab, lab / "sim" / "files.f"))

    lab05 = root / "labs" / "Lab05_W9_W10"
    lab05_file_list = lab05 / "sim" / "files.f"
    if lab05_file_list.is_file():
        for name, data_width, enable_2to4 in (
            ("Lab05 dense INT8", 8, 0),
            ("Lab05 dense INT4", 4, 0),
            ("Lab05 2:4 INT8", 8, 1),
            ("Lab05 2:4 INT4", 4, 1),
        ):
            cases.append(
                HDLCase(
                    name,
                    lab05,
                    lab05_file_list,
                    (
                        "-Wall",
                        "-s",
                        "tb_ai_accel_top",
                        f"-Ptb_ai_accel_top.DATA_WIDTH={data_width}",
                        f"-Ptb_ai_accel_top.ENABLE_2TO4={enable_2to4}",
                    ),
                )
            )
    return cases


def run_hdl_case(
    case: HDLCase,
    simulator: Simulator,
    output_path: Path,
    timeout: float,
) -> TestResult:
    if not case.working_directory.is_dir():
        return TestResult(case.name, "FAIL", f"missing working directory: {case.working_directory}")
    if not case.file_list.is_file():
        return TestResult(case.name, "FAIL", f"missing file list: {case.file_list}")
    assert simulator.iverilog is not None
    assert simulator.vvp is not None

    compile_command: list[str] = [str(simulator.iverilog)]
    if simulator.ivl_base is not None:
        compile_command.extend(("-B", str(simulator.ivl_base)))
    compile_command.append("-g2012")
    compile_command.extend(case.compiler_arguments)
    compile_command.extend(("-o", str(output_path), "-f", str(case.file_list)))
    compile_result = run_command(
        case.name + " (compile)",
        compile_command,
        case.working_directory,
        timeout,
    )
    if compile_result.status != "PASS":
        return TestResult(
            case.name,
            "FAIL",
            "compile step failed: " + compile_result.detail,
            compile_result.duration,
            compile_result.command,
            compile_result.output,
        )

    simulate_command: list[str] = [str(simulator.vvp)]
    if simulator.vvp_module_dir is not None:
        simulate_command.extend(("-M", str(simulator.vvp_module_dir)))
    simulate_command.append(str(output_path))
    simulation = run_command(
        case.name,
        simulate_command,
        case.working_directory,
        timeout,
        require_pass_text=True,
    )
    return TestResult(
        case.name,
        simulation.status,
        simulation.detail,
        compile_result.duration + simulation.duration,
        command_text(compile_command) + "\n" + simulation.command,
        compile_result.output + simulation.output,
    )


def python_test_commands(root: Path, temp_dir: Path) -> list[tuple[str, list[str], Path, bool]]:
    python = sys.executable
    lab01 = root / "labs" / "Lab01_W1_W2"
    lab05 = root / "labs" / "Lab05_W9_W10"
    lab06 = root / "labs" / "Lab06_W11_W12"
    return [
        (
            "Static project verification",
            [python, str(root / "scripts" / "verify_project.py"), "--root", str(root)],
            root,
            True,
        ),
        (
            "Lab01 Python smoke test",
            [python, str(lab01 / "scripts" / "smoke_test.py")],
            lab01,
            True,
        ),
        (
            "Lab05 collect_ppa self-test",
            [python, str(lab05 / "scripts" / "collect_ppa.py"), "--self-test"],
            lab05,
            True,
        ),
        (
            "Lab06 analyze_tradeoffs self-test",
            [python, str(lab06 / "scripts" / "analyze_tradeoffs.py"), "--self-test"],
            lab06,
            True,
        ),
        (
            "Lab06 illustrative CSV analysis",
            [
                python,
                str(lab06 / "scripts" / "analyze_tradeoffs.py"),
                str(lab06 / "data" / "ppa_results_sample.csv"),
                "--output-dir",
                str(temp_dir / "tradeoff_results"),
                "--no-plot",
            ],
            lab06,
            False,
        ),
        (
            "Lab06 repository checker",
            [python, str(lab06 / "scripts" / "check_repo.py"), "--root", str(root)],
            lab06,
            True,
        ),
    ]


def print_result(result: TestResult) -> None:
    print(f"[{result.status:4s}] {result.name} ({result.duration:.2f}s): {result.detail}")
    if result.status == "FAIL":
        if result.command:
            print("       command: " + result.command.replace("\n", "\n                "))
        if result.output.strip():
            lines = result.output.rstrip().splitlines()
            if len(lines) > 80:
                lines = [f"... {len(lines) - 80} earlier line(s) omitted ...", *lines[-80:]]
            for line in lines:
                print("       | " + line)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="course project root")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds allowed per command")
    parser.add_argument("--iverilog", help="iverilog executable path or command name")
    parser.add_argument("--vvp", help="vvp executable path or command name")
    parser.add_argument("--iverilog-base", help="local ivl helper directory passed with iverilog -B")
    parser.add_argument("--vvp-module-dir", help="local VPI module directory passed with vvp -M")
    parser.add_argument(
        "--require-simulator",
        action="store_true",
        help="make an unavailable HDL simulator affect the exit status",
    )
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"[FAIL] project root is not a directory: {root}")
        return 2
    if args.timeout <= 0:
        print("[FAIL] --timeout must be greater than zero")
        return 2

    results: list[TestResult] = []
    with tempfile.TemporaryDirectory(prefix="fpga_ai_course_tests_") as temporary:
        temp_dir = Path(temporary)
        for name, command, cwd, require_pass in python_test_commands(root, temp_dir):
            result = run_command(name, command, cwd, args.timeout, require_pass_text=require_pass)
            results.append(result)
            print_result(result)

        simulator = detect_simulator(args, root)
        if simulator.error:
            setup = TestResult("HDL simulator setup", "FAIL", simulator.error)
            results.append(setup)
            print_result(setup)

        if simulator.available:
            options = []
            if simulator.ivl_base:
                options.append(f"-B {simulator.ivl_base}")
            if simulator.vvp_module_dir:
                options.append(f"-M {simulator.vvp_module_dir}")
            option_text = ", ".join(options) if options else "system defaults"
            print(f"HDL tools: iverilog={simulator.iverilog}; vvp={simulator.vvp}; {option_text}")
            for index, case in enumerate(hdl_cases(root), start=1):
                output_path = temp_dir / f"hdl_{index:02d}.vvp"
                result = run_hdl_case(case, simulator, output_path, args.timeout)
                results.append(result)
                print_result(result)
        else:
            missing = []
            if simulator.iverilog is None:
                missing.append("iverilog")
            elif not simulator.iverilog.is_file():
                missing.append(f"iverilog ({simulator.iverilog})")
            if simulator.vvp is None:
                missing.append("vvp")
            elif not simulator.vvp.is_file():
                missing.append(f"vvp ({simulator.vvp})")
            detail = "simulator unavailable: " + ", ".join(missing or ["invalid local configuration"])
            for case in hdl_cases(root):
                result = TestResult(case.name, "SKIP", detail)
                results.append(result)
                print_result(result)
            if args.require_simulator and simulator.error is None:
                required = TestResult("HDL simulator required", "FAIL", detail)
                results.append(required)
                print_result(required)

    failures = [result for result in results if result.status == "FAIL"]
    skipped = [result for result in results if result.status == "SKIP"]
    passed = [result for result in results if result.status == "PASS"]
    if failures:
        overall = "FAIL"
    elif skipped:
        overall = "INCOMPLETE (HDL SKIPPED)"
    else:
        overall = "PASS"
    print(
        f"SUMMARY: {overall} "
        f"({len(passed)} passed, {len(failures)} failed, {len(skipped)} skipped)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
