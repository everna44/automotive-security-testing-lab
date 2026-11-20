"""vcan0에서 Lab 02의 정상 읽기·쓰기 및 경계값을 검사한다."""

import argparse
import json
from pathlib import Path
import subprocess
import time

import can


def require_vcan():
    output = subprocess.check_output(
        ["ip", "-json", "-details", "link", "show", "dev", "vcan0"], text=True,
    )
    interface, = json.loads(output)
    if interface.get("linkinfo", {}).get("info_kind") != "vcan" or "UP" not in interface["flags"]:
        raise ValueError("활성화된 가상 CAN 인터페이스 vcan0가 필요합니다.")


def describe(frame):
    return {
        "id": frame.arbitration_id,
        "dlc": frame.dlc,
        "payload": frame.data.hex(" ").upper(),
        "extended": frame.is_extended_id,
        "fd": frame.is_fd,
        "remote": frame.is_remote_frame,
        "error": frame.is_error_frame,
    }


def run(bus, results):
    rows = []
    last_send = time.monotonic() - 0.1
    steps = (
        ("초기화 쓰기", 2, 50, 50),
        ("사전 읽기", 1, 0, 50),
        ("하한 쓰기", 2, 0, 0),
        ("하한 읽기", 1, 0, 0),
        ("상한 쓰기", 2, 100, 100),
        ("상한 읽기", 1, 0, 100),
        ("복원 쓰기", 2, 50, 50),
        ("최종 읽기", 1, 0, 50),
    )
    for seq, (label, command, value, current) in enumerate(steps, 1):
        request = can.Message(
            arbitration_id=0x120, is_extended_id=False, check=True,
            data=bytes([seq, command]) + value.to_bytes(2, "big"),
        )
        expected = describe(can.Message(
            arbitration_id=0x121, is_extended_id=False,
            data=bytes([seq, 0]) + current.to_bytes(2, "big"),
        ))
        actual = []
        sent = False
        try:
            while (delay := last_send + 0.1 - time.monotonic()) > 0:
                time.sleep(delay)
            bus.send(request, timeout=1.0)
            sent = True
            last_send = time.monotonic()
            deadline = last_send + 1.0
            while (remaining := deadline - time.monotonic()) > 0:
                frame = bus.recv(timeout=remaining)
                if frame is None:
                    break
                actual.append(describe(frame))
            reason = (
                "기대 응답 일치" if actual == [expected] else
                "응답 수·형식·내용 불일치" if actual else "응답 타임아웃"
            )
        except (can.CanError, OSError) as error:
            reason = f"송수신 오류로 관찰 불충분 ({error})"
        passed = reason == "기대 응답 일치"
        row = {
            "case": label, "request": describe(request), "send_completed": sent, "expected": expected,
            "actual": actual, "result": "PASS" if passed else "FAIL", "reason": reason,
        }
        results.write(json.dumps(row, ensure_ascii=False) + "\n")
        results.flush()
        rows.append(row)
        if not passed:
            break
    return rows, len(steps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="새 결과 디렉터리")
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    error = None
    rows = []
    planned = 8
    with (args.output / "results.jsonl").open("x", encoding="utf-8") as results:
        try:
            require_vcan()
            with can.Bus(
                interface="socketcan", channel="vcan0", fd=True, ignore_config=True,
                can_filters=[{"can_id": 0x121, "can_mask": 0x7FF}],
            ) as bus:
                rows, planned = run(bus, results)
        except (can.CanError, OSError, ValueError, subprocess.CalledProcessError) as exc:
            error = str(exc)
    passed = sum(row["result"] == "PASS" for row in rows)
    summary = (
        "| 계획 | PASS | FAIL | 미실시 |\n|---:|---:|---:|---:|\n"
        f"| {planned} | {passed} | {len(rows) - passed} | {planned - len(rows)} |\n"
    )
    if error:
        summary += f"\nSocketCAN 초기화 또는 종료 오류\n\n{error}\n"
    (args.output / "summary.md").write_text(summary, encoding="utf-8")
    print(summary, end="")
    return int(error is not None or passed != planned)


if __name__ == "__main__":
    raise SystemExit(main())
