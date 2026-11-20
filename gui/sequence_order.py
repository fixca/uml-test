"""시퀀스 참여자를 캔버스 항목과 연결하는 키."""


def participant_key(name: str) -> str:
    return f"sequence:{name}"
