"""SocketCAN에서 읽기·쓰기 요청과 입력 검증을 처리하는 소프트웨어 가상 ECU."""

import argparse

import can


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="vcan0")
    args = parser.parse_args()
    setting_value = 50
    with can.Bus(interface="socketcan", channel=args.channel) as bus:
        print(f"READY channel={args.channel} setting_value={setting_value}", flush=True)
        try:
            for request in bus:
                if (
                    request.arbitration_id != 0x120
                    or request.is_extended_id
                    or request.is_fd
                    or request.is_remote_frame
                    or request.is_error_frame
                ):
                    continue
                seq = request.data[0] if request.data else 0x00
                status = 0x00
                if request.dlc != 4 or len(request.data) != 4:
                    status = 0x01
                else:
                    command = request.data[1]
                    value = int.from_bytes(request.data[2:4], "big")
                    if command not in (0x01, 0x02):
                        status = 0x02
                    elif command == 0x01 and value != 0:
                        status = 0x04
                    elif command == 0x02 and value > 100:
                        status = 0x03
                    elif command == 0x02:
                        setting_value = value
                payload = bytes([seq, status]) + setting_value.to_bytes(2, "big")
                bus.send(can.Message(arbitration_id=0x121, is_extended_id=False,
                                     data=payload), timeout=1.0)
                print(f"RX 120#{request.data.hex(' ').upper()} "
                      f"TX 121#{payload.hex(' ').upper()}", flush=True)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
