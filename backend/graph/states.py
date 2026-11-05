from typing import List, TypedDict, Any, Dict


class GeneralStates(TypedDict):
    request: str
    session_id: str

    next_agent: str
    agent_task: List[Dict[str, Any]]

    # answer agent
    answer: str

    feedback: str
    approved_agent_answer: bool

    retry_count: int
    max_retry_count: int
