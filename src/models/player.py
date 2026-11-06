from typing import TypedDict, List, Dict, Optional, Annotated

class Player(TypedDict):
    id: str          # 如 "1号(天狼)"
    role: str        # werewolf, villager, seer, witch, hunter
    alive: bool


