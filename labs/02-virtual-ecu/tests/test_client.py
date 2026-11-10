"""SocketCAN ECU의 읽기·쓰기 및 입력 검증 시험 (응답 제한 1초)."""

import argparse
import time

import can


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="vcan0")
    args = parser.parse_args()
    checks = 0
    failures = 0
    sequence = 0

    with can.Bus(interface="socketcan", channel=args.channel, fd=True) as bus:
        def exchange(label, data, status=0, current=50, silent=False, **flags):
            nonlocal checks, failures, sequence
            sequence = (sequence + 1) % 256
            payload = bytes([sequence]) + data[1:] if data else b""
            seq = sequence if payload else 0
            expected = None if silent else bytes([seq, status]) + current.to_bytes(2, "big")
            message = can.Message(arbitration_id=flags.pop("arbitration_id", 0x120),
                                  is_extended_id=flags.pop("is_extended_id", False),
                                  data=payload, **flags)
            # 이전 케이스의 지연 프레임도 숨기지 않고 실패로 보고한다.
            stale = []
            while (frame := bus.recv(timeout=0)) is not None:
                if frame.arbitration_id == 0x121:
                    stale.append(frame)
            bus.send(message, timeout=1.0)
            deadline = time.monotonic() + 1.0
            responses = []
            while (remaining := deadline - time.monotonic()) > 0:
                frame = bus.recv(timeout=remaining)
                if frame is None:
                    break
                if frame.arbitration_id == 0x121:
                    responses.append(frame)
            valid = (not responses if silent else len(responses) == 1 and
                     not any((responses[0].is_extended_id, responses[0].is_fd,
                              responses[0].is_remote_frame, responses[0].is_error_frame)) and
                     responses[0].dlc == 4 and bytes(responses[0].data) == expected)
            valid = valid and not stale
            checks += 1
            failures += not valid
            actual = [f"{r.data.hex(' ').upper()} (DLC={r.dlc}, EFF={r.is_extended_id}, "
                      f"FD={r.is_fd}, RTR={r.is_remote_frame}, ERR={r.is_error_frame})"
                      for r in responses]
            reason = "없음" if valid else ("이전 응답 잔류" if stale else
                     "응답 타임아웃" if not responses and not silent else "응답 수·형식·내용 불일치")
            print(f"{'PASS' if valid else 'FAIL'} {label}: "
                  f"TX={message.arbitration_id:03X}#{message.data.hex(' ').upper()} DLC={message.dlc} "
                  f"EFF={message.is_extended_id} FD={message.is_fd} "
                  f"RTR={message.is_remote_frame} ERR={message.is_error_frame} "
                  f"예상={expected.hex(' ').upper() if expected is not None else '무응답(1초)'} "
                  f"실제={actual or '무응답(1초)'} 실패 이유={reason}", flush=True)
            return valid

        cases = [
            ("정상 읽기", bytes([0, 1, 0, 0]), {}, 50),
            ("정상 쓰기 75", bytes([0, 2, 0, 75]), {"current": 75}, 75),
            ("경계 쓰기 0", bytes([0, 2, 0, 0]), {"current": 0}, 0),
            ("경계 쓰기 100", bytes([0, 2, 0, 100]), {"current": 100}, 100),
            ("범위 초과 101", bytes([0, 2, 0, 101]), {"status": 3}, 50),
            ("범위 초과 65535", bytes([0, 2, 255, 255]), {"status": 3}, 50),
            ("미지원 CMD", bytes([0, 255, 0, 0]), {"status": 2}, 50),
            ("읽기 VALUE 오류", bytes([0, 1, 0, 1]), {"status": 4}, 50),
        ]
        for length in (0, 1, 2, 3, 5, 6, 7, 8):
            # 미지원 CMD와 비영 VALUE를 함께 넣어 길이 오류 우선순위 확인.
            cases.append((f"길이 {length}", bytes([0, 255, 255, 255, 0, 0, 0, 0])[:length],
                          {"status": 1}, 50))
        for label, flags in (
            ("미지원 ID", {"arbitration_id": 0x122}),
            ("RTR", {"is_remote_frame": True}),
            ("확장 프레임", {"is_extended_id": True}),
            ("CAN FD", {"is_fd": True}),
            ("오류 프레임", {"is_error_frame": True}),
        ):
            cases.append((label, bytes([0, 2, 0, 75]), {"silent": True, **flags}, 50))
        for label, data, options, after in cases:
            if not exchange(f"{label}/초기화 쓰기", bytes([0, 2, 0, 50])):
                break
            if not exchange(f"{label}/초기화 읽기", bytes([0, 1, 0, 0])):
                break
            exchange(label, data, **options)
            exchange(f"{label}/후속 읽기", bytes([0, 1, 0, 0]), current=after)
    print(f"SUMMARY checks={checks} failures={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
