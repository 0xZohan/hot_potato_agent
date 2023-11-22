# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This module contains the transaction payloads of the ConsensusTendermintServiceAbciApp."""

from dataclasses import dataclass
from typing import Optional

from packages.valory.skills.abstract_round_abci.base import BaseTxPayload

@dataclass(frozen=True)
class CheckResultsPayload(BaseTxPayload):
    """Represent a transaction payload for the CheckResultsRound."""
    over_threshold: bool  # Attribute indicating if the sender's balance is over 1xDAI

@dataclass(frozen=True)
class StartVotingPayload(BaseTxPayload):
    """Represent a transaction payload for the StartVotingRound."""
    sender: str  # The agent sending the payload
    vote_for_receiver: str  # Vote cast by the sender on which agent should receive the next 1xDAI

@dataclass(frozen=True)
class TransferFundsPayload(BaseTxPayload):
    """Represent a transaction payload for the TransferFundsRound."""
    sender: str  # The agent responsible for sending the funds
    transaction_hash: str  # Hash of the transaction of the on-chain fund transfer
    receiver: str  # The recipient agent of the 1xDAI

@dataclass(frozen=True)
class WaitForFundsPayload(BaseTxPayload):
    """Represent a transaction payload for the WaitForFundsRound."""
    sender: str  # The agent sending the payload
    received: bool  # Confirmation on whether the sender has received the funds
    transaction_hash: Optional[str] = None  # Transaction hash if the funds are received