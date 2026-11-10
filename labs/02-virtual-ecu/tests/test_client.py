"""실제 vcan0의 ECU에 읽기 요청을 보내고 1초 이내 응답을 검증한다."""

import argparse
import time

import can


def main():
    parser = argparse.ArgumentParser(description="읽기 응답 검증 (타임아웃 1초)")
    parser.add_argument("--channel", default="vcan0")
    args = parser.parse_args()
    expected = bytes.fromhex("10 00 00 32")
    with can.Bus(interface="socketcan", channel=args.channel) as bus:
        bus.send(can.Message(arbitration_id=0x120, is_extended_id=False,
                             data=bytes.fromhex("10 01 00 00")), timeout=1.0)
        print("TX 120#10 01 00 00", flush=True)
        deadline = time.monotonic() + 1.0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SystemExit("FAIL: 응답 타임아웃 (1초)")
            response = bus.recv(timeout=remaining)
            if response is None:
                raise SystemExit("FAIL: 응답 타임아웃 (1초)")
            if (response.arbitration_id != 0x121 or response.is_extended_id
                    or response.is_fd or response.is_remote_frame or response.is_error_frame):
                continue
            print(f"RX 121#{response.data.hex(' ').upper()}", flush=True)
            if response.dlc != 4 or bytes(response.data) != expected:
                raise SystemExit("FAIL: 응답이 기대값 10 00 00 32와 다름")
            print("PASS: 기대 응답 일치", flush=True)
            return


if __name__ == "__main__":
    main()
