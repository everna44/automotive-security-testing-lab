"""Lab 02 ECU의 입력 검증을 메모리에서 실행한다."""

import argparse
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import random
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import patch


SEED = 20261120
ECU = Path(__file__).resolve().parents[2] / "02-virtual-ecu" / "src" / "ecu.py"


@dataclass
class Frame:
    arbitration_id: int
    is_extended_id: bool
    data: bytes
    is_fd: bool = False
    is_remote_frame: bool = False
    is_error_frame: bool = False

    @property
    def dlc(self):
        return len(self.data)

    def describe(self):
        return {**vars(self), "data": self.data.hex(" ").upper(), "dlc": self.dlc}


class InMemoryBus:
    def __init__(self, requests):
        self.requests = requests
        self.responses = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def __iter__(self):
        for request in self.requests:
            self.responses.append([])
            yield request

    def send(self, response, timeout):
        self.responses[-1].append(response.describe())


def payload(seq, command, value):
    return bytes([seq, command]) + value.to_bytes(2, "big")


def cases():
    rng = random.Random(SEED)
    unsupported = [0, *range(3, 256)]
    inputs = [
        ("초기 읽기", 1, 0, 4, 0),
        ("하한 쓰기", 2, 0, 4, 0),
        ("상한 쓰기", 2, 100, 4, 0),
        ("상한 초과", 2, 101, 4, 3),
        ("최대 VALUE 쓰기", 2, 65535, 4, 3),
        ("읽기 VALUE 오류", 1, 1, 4, 4),
        ("최대 VALUE 읽기 오류", 1, 65535, 4, 4),
    ]
    for length in (0, 1, 2, 3, 5, 6, 7, 8):
        inputs.append(("길이 오류 우선", 255, 65535, length, 1))
    for _ in range(32):
        length = rng.choice((0, 1, 2, 3, 5, 6, 7, 8))
        inputs.extend([
            ("정상 읽기", 1, 0, 4, 0),
            ("정상 쓰기", 2, rng.randint(0, 100), 4, 0),
            ("미지원 CMD", rng.choice(unsupported), rng.randrange(65536), 4, 2),
            ("쓰기 VALUE 오류", 2, rng.randint(101, 65535), 4, 3),
            ("읽기 VALUE 오류", 1, rng.randint(1, 65535), 4, 4),
            ("길이 오류", rng.randrange(256), rng.randrange(65536), length, 1),
        ])

    current = 50
    for index, (label, command, value, length, status) in enumerate(inputs, 1):
        seq = rng.randrange(256)
        data = payload(seq, command, value)[:length]
        data += bytes(rng.randrange(256) for _ in range(length - len(data)))
        if status == 0 and command == 2:
            current = value
        yield index, label, data, payload(seq if data else 0, status, current)
        if status or command == 2:
            read_seq = rng.randrange(256)
            yield index, "후속 읽기", payload(read_seq, 1, 0), payload(read_seq, 0, current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="새 결과 디렉터리")
    args = parser.parse_args()
    args.output.mkdir(parents=True)

    checks = list(cases())
    bus = InMemoryBus([Frame(0x120, False, data) for _, _, data, _ in checks])
    fake_can = SimpleNamespace(Bus=lambda **_: bus, Message=Frame)
    error = None
    try:
        with patch.dict(sys.modules, {"can": fake_can}), patch.object(sys, "argv", [str(ECU)]):
            with redirect_stdout(StringIO()):
                runpy.run_path(str(ECU), run_name="__main__")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    rows = []
    for position, (index, label, data, response) in enumerate(checks):
        expected = Frame(0x121, False, response).describe()
        actual = bus.responses[position] if position < len(bus.responses) else None
        rows.append({
            "case": index,
            "check": label,
            "request": Frame(0x120, False, data).describe(),
            "expected": [expected],
            "actual": actual,
            "result": "PASS" if actual == [expected] else "FAIL",
        })

    passed = sum(row["result"] == "PASS" for row in rows)
    failed = len(rows) - passed
    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "ecu_sha256": sha256(ECU.read_bytes()).hexdigest(),
        "seed": SEED,
        "transport": "in-memory",
        "cases": checks[-1][0],
        "passed": passed,
        "failed": failed,
        "execution_error": error,
        "checks": rows,
    }
    with (args.output / "results.json").open("x", encoding="utf-8") as log:
        json.dump(report, log, ensure_ascii=False, indent=2)
        log.write("\n")

    summary = (
        "| 시드 | 입력 케이스 | 전체 검사 | PASS | FAIL |\n"
        "|---:|---:|---:|---:|---:|\n"
        f"| {SEED} | {report['cases']} | {len(rows)} | {passed} | {failed} |\n"
    )
    table = (
        "\n| 케이스 | 검사 | 요청 Payload | 기대 Payload | 실제 Payload | 판정 |\n"
        "|---:|---|---|---|---|---|\n"
    )
    for row in rows:
        actual = row["actual"]
        actual_payloads = ", ".join(frame["data"] for frame in actual or [])
        actual_text = "미처리" if actual is None else actual_payloads or "응답 없음"
        table += (
            f"| {row['case']} | {row['check']} | {row['request']['data'] or '빈 Payload'} | "
            f"{row['expected'][0]['data']} | {actual_text} | {row['result']} |\n"
        )
    with (args.output / "summary.md").open("x", encoding="utf-8") as log:
        log.write(summary)
        if error:
            log.write(f"\nECU 실행 오류 `{error}`\n")
        log.write(table)
    print(summary, end="")
    return int(failed > 0 or error is not None)


if __name__ == "__main__":
    raise SystemExit(main())
