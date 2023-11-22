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

"""This package contains the rounds of ConsensusTendermintServiceAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from collections import Counter

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AbstractRound,
    AppState,
    BaseSynchronizedData,
    DegenerateRound,
    EventToTimeout,
    OnlyKeeperSendsRound,
    VotingRound,
)

from packages.valory.skills.hot_potato_abci.payloads import (
    CheckResultsPayload,
    StartVotingPayload,
    TransferFundsPayload,
    WaitForFundsPayload,
)


class Event(Enum):
    """ConsensusTendermintServiceAbciApp Events"""

    ROUND_TIMEOUT = "round_timeout"
    DONE = "done"
    NO_MAJORITY = "no_majority"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """


class CheckResultsRound(VotingRound):
    """CheckResultsRound"""

    payload_class = CheckResultsPayload
    payload_attribute = "over_threshold"  # Payload attribute updated as per the actual content
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        selected_receiver = self.synchronized_data.count_votes()
        if selected_receiver:
            # Update the receiver for the transfer
            # This would likely be part of the synchronized data
            self.synchronized_data.selected_receiver = selected_receiver
            return self.synchronized_data, Event.DONE
        return self.synchronized_data, Event.NO_MAJORITY
    
    def check_payload(self, payload: CheckResultsPayload) -> None:
        """Check payload."""
        # Ensure the payload is valid; in this case, it should be a boolean indicating if the balance is over 1xDAI
        if not isinstance(payload.content, bool):
            raise ValueError("Payload content is not a boolean indicating balance threshold status.")
    
    def process_payload(self, payload: CheckResultsPayload) -> None:
        """Process payload."""
        # Here, we process the payload to keep track of whether any agent has a balance over the threshold
        if payload.over_threshold:
            self.synchronized_data.add_vote(payload.sender, True)
        else:
            self.synchronized_data.add_vote(payload.sender, False)


class StartVotingRound(VotingRound):
    """StartVotingRound"""

    payload_class = StartVotingPayload
    payload_attribute = "receiver"  # Payload attribute updated as per the actual content
    synchronized_data_class = SynchronizedData

    # Based on the logic, this is similar to CheckResultsRound
    # Here agents need to vote on who should receive the DAI during this round

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        raise NotImplementedError

    def check_payload(self, payload: StartVotingPayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: StartVotingPayload) -> None:
        """Process payload."""
        raise NotImplementedError


class TransferFundsRound(OnlyKeeperSendsRound):
    """TransferFundsRound"""

    payload_class = TransferFundsPayload
    payload_attribute = "transaction_payload"  # Updated to represent the DAI transfer payload
    synchronized_data_class = SynchronizedData

    # Since only the keeper sends in this round,
    # the keeper will execute the on-chain transaction and provide evidence of the transfer

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        raise NotImplementedError

    def check_payload(self, payload: TransferFundsPayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: TransferFundsPayload) -> None:
        """Process payload."""
        raise NotImplementedError


class WaitForFundsRound(DegenerateRound):
    """WaitForFundsRound"""

    payload_class = WaitForFundsPayload
    payload_attribute = "confirmation"  # Assume this is a simple boolean confirmation
    synchronized_data_class = SynchronizedData

    # In this round, agents would typically wait for confirmation of the transfer on-chain

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        raise NotImplementedError

    def check_payload(self, payload: WaitForFundsPayload) -> None:
        """Check payload."""
        raise NotImplementedError

    def process_payload(self, payload: WaitForFundsPayload) -> None:
        """Process payload."""
        raise NotImplementedError


class ConsensusTendermintServiceAbciApp(AbciApp[Event]):
    """ConsensusTendermintServiceAbciApp"""

    initial_round_cls: AppState = WaitForFundsRound
    initial_states: Set[AppState] = {WaitForFundsRound}
    transition_function: AbciAppTransitionFunction = {
        WaitForFundsRound: {
            Event.DONE: StartVotingRound
        },
        StartVotingRound: {
            Event.DONE: CheckResultsRound,
            Event.NO_MAJORITY: StartVotingRound,
            Event.ROUND_TIMEOUT: WaitForFundsRound
        },
        CheckResultsRound: {
            Event.DONE: TransferFundsRound,
            Event.NO_MAJORITY: StartVotingRound
        },
        TransferFundsRound: {
            Event.DONE: WaitForFundsRound,
            Event.ROUND_TIMEOUT: WaitForFundsRound
        }
    }
    final_states: Set[AppState] = set()
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        WaitForFundsRound: [],
    }
    db_post_conditions: Dict[AppState, Set[str]] = {

    }
