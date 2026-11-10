"""SocketCAN에서 읽기 요청만 처리하는 소프트웨어 가상 ECU."""

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
                    or request.dlc != 4
                    or len(request.data) != 4
                    or request.data[1] != 0x01
                    or int.from_bytes(request.data[2:4], "big") != 0
                ):
                    continue
                payload = bytes([request.data[0], 0x00]) + setting_value.to_bytes(2, "big")
                bus.send(can.Message(arbitration_id=0x121, is_extended_id=False,
                                     data=payload), timeout=1.0)
                print(f"RX 120#{request.data.hex(' ').upper()} "
                      f"TX 121#{payload.hex(' ').upper()}", flush=True)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
