# Lab 04-2 — 가상 ECU 입력 검증과 CAN 통신

Lab 02의 소프트웨어 가상 ECU를 사용했습니다. 요청 ID는 `0x120`, 응답 ID는 `0x121`입니다. [Lab 02 통신 규격](../../02-virtual-ecu/README.md#통신-규격)

## 메모리 기반 자동 입력 검증

[regression.py](regression.py)는 Lab 02 ECU의 요청 처리 루프를 실행하면서 CAN 버스와 메시지를 메모리 대역으로 바꿉니다. CAN 송신 없이 입력 경계값과 오류 응답을 검사하고, 후속 읽기로 현재값을 확인했습니다.

| 기록된 검사 | 요청 Payload | 실제 응답 Payload | 결과 |
|---|---|---|---|
| 상한 100 쓰기 | `C3 02 00 64` | `C3 00 00 64` | 쓰기 성공, 현재값 100 |
| 상한 초과 101 쓰기 | `10 02 00 65` | `10 03 00 64` | 범위 오류, 현재값 100 |
| 상한 초과 후 읽기 | `9B 01 00 00` | `9B 00 00 64` | 현재값 100 유지 |
| 길이 0 입력 | 빈 값 | `00 01 00 64` | 길이 오류, 현재값 100 |

시드 `20261120`으로 입력 207개와 후속 읽기 174개를 검사했습니다. **381 PASS, 0 FAIL**이 기록됐습니다. [요약](results/regression-20261120T014649511378269Z/summary.md) · [기대·실제 응답 JSON](results/regression-20261120T014649511378269Z/results.json)

메모리 검사를 재현하려면 저장소 루트에서 일반 사용자 권한으로 Python 3을 사용합니다. 새 디렉터리에 요약과 JSON이 생성되며 같은 ECU 코드에서 381 PASS를 기대합니다.

```bash
lab=labs/04-autohack-analysis/04-2-virtual-ecu-fuzzing
python3 "$lab/regression.py" "$lab/results/regression-$(date -u +%Y%m%dT%H%M%S%NZ)"
```

## 가상 CAN 정상 통신 검사

[check_ecu.py](check_ecu.py)가 SocketCAN의 가상 인터페이스 `vcan0`에서 50 → 0 → 100 → 50 순서로 쓰고 각 값을 읽었습니다. 정상 요청 8건에서 **8 PASS, 0 FAIL**이 기록됐습니다.

| 기록된 검사 | 요청 Payload | 실제 응답 Payload |
|---|---|---|
| 하한 0 쓰기 | `03 02 00 00` | `03 00 00 00` |
| 상한 100 쓰기 | `05 02 00 64` | `05 00 00 64` |
| 복원 후 읽기 | `08 01 00 00` | `08 00 00 32` |

[요약](results/20261119T180634949025Z/check/summary.md) · [요청·응답 JSONL](results/20261119T180634949025Z/check/results.jsonl) · [ECU 로그](results/20261119T180634949025Z/ecu.log)

Ubuntu에서 재현하려면 Lab 02 절차에 따라 활성 `vcan0`과 `python-can` 환경을 준비하고 ECU를 한 개 실행합니다. 장치 준비에는 관리자 권한이 필요할 수 있습니다. 저장소 루트의 별도 터미널에서 일반 사용자로 아래 명령을 실행하면 새 디렉터리에 결과가 생성됩니다. 기대 결과는 8 PASS입니다. [Lab 02 실행 절차](../../02-virtual-ecu/README.md#실행-절차)

```bash
lab=labs/04-autohack-analysis/04-2-virtual-ecu-fuzzing
labs/02-virtual-ecu/.venv/bin/python "$lab/check_ecu.py" "$lab/results/$(date -u +%Y%m%dT%H%M%S%NZ)/check"
```

## 가상 CAN 수동 입력 검증

사용자가 `vcan0`에서 소프트웨어 가상 ECU에 수동으로 보낸 요청을 Wireshark로 캡처했습니다. PCAPNG에는 SocketCAN 프레임 12개가 순서대로 기록됐습니다. 요청 6개의 ID는 `0x120`, 응답 6개의 ID는 `0x121`입니다. 아래 기대 응답은 Lab 02 통신 규격과 시작값 50을 기준으로 산정했습니다. 응답 DLC는 기대값과 캡처 모두 6건에서 4입니다.

| 프레임 (요청 → 응답) | 검사 | 요청 DLC | 요청 Payload | 기대 응답 Payload | 캡처 응답 Payload | 결과 |
|---|---|---:|---|---|---|---|
| 1 → 2 | 정상 읽기 | 4 | `10 01 00 00` | `10 00 00 32` | `10 00 00 32` | 성공, 현재값 50 |
| 3 → 4 | 범위 초과 쓰기 (101) | 4 | `11 02 00 65` | `11 03 00 32` | `11 03 00 32` | 범위 오류, 현재값 50 |
| 5 → 6 | 상태 유지 확인 | 4 | `12 01 00 00` | `12 00 00 32` | `12 00 00 32` | 쓰기 거부 후 50 유지 |
| 7 → 8 | 미지원 명령 | 4 | `13 FF 00 00` | `13 02 00 32` | `13 02 00 32` | 미지원 명령 오류 |
| 9 → 10 | 길이 오류 | 3 | `14 01 00` | `14 01 00 32` | `14 01 00 32` | 길이 오류 응답 |
| 11 → 12 | 최종 읽기 | 4 | `15 01 00 00` | `15 00 00 32` | `15 00 00 32` | 오류 요청 후에도 50 유지 |

6개 응답의 CAN ID, DLC, Payload가 모두 기대값과 일치했습니다. Wireshark 화면의 프레임 번호, 상대 시간, CAN ID, DLC와 첫 요청 Payload도 PCAPNG와 일치합니다. [PCAPNG 원본](captures/ecu-input-validation.pcapng) · [Wireshark 스크린샷](screenshots/01-ecu-input-validation.png)

메모리 기반 381 PASS, `vcan0` 정상 통신 8 PASS, 수동 입력 검증 6건은 각각 독립된 결과입니다. 이 수동 캡처의 범위는 표에 있는 6개 요청이며, 메모리 검사 전체의 `vcan0` 검증과 실제 차량·물리 ECU 시험은 미검증입니다.
