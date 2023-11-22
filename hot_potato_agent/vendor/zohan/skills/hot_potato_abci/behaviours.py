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

"""This package contains round behaviours of ConsensusTendermintServiceAbciApp."""

from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)

from packages.valory.skills.hot_potato_abci.models import Params
from packages.valory.skills.hot_potato_abci.rounds import (
    SynchronizedData,
    ConsensusTendermintServiceAbciApp,
    CheckResultsRound,
    StartVotingRound,
    TransferFundsRound,
    WaitForFundsRound,
)
from packages.valory.skills.hot_potato_abci.rounds import (
    CheckResultsPayload,
    StartVotingPayload,
    TransferFundsPayload,
    WaitForFundsPayload,
)


class ConsensusTendermintServiceBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the hot_potato skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

class CheckResultsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """CheckResultsBehaviour"""

    matching_round: Type[AbstractRound] = CheckResultsRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Check if the current agent has more than 1xDAI
            balance = self.synchronized_data.get_balance(sender)
            over_threshold = balance > 1
            # The content is boolean, whether the agent has more than 1xDAI
            payload = CheckResultsPayload(sender=sender, content=over_threshold)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class StartVotingBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """StartVotingBehaviour"""

    matching_round: Type[AbstractRound] = StartVotingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Agents vote on who should receive the pot next
            # The payload will contain the agent identifier to receive the DAI
            receiver = self.synchronized_data.get_next_receiver()
            payload = StartVotingPayload(sender=sender, content=receiver)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class TransferFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """TransferFundsBehaviour"""

    matching_round: Type[AbstractRound] = TransferFundsRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # The agent with more than 1xDAI will transfer DAI to the decided receiver
            receiver = self.synchronized_data.get_decided_receiver()
            # Check if I am the one with more than 1xDAI
            if self.synchronized_data.get_balance(sender) > 1:
                # Perform the fund transfer here - the actual implementation will depend on how you interact with the blockchain
                # For example, this could be an Ethereum transaction sending 1xDAI to the `receiver`
                transaction_payload = {
                    'to': receiver,
                    'value': 1, # In the units your blockchain expects, e.g., Wei for Ethereum
                    # Add other transaction parameters as necessary
                }
                payload = TransferFundsPayload(sender=sender, content=transaction_payload)
            else:
                payload = TransferFundsPayload(sender=sender, content=None)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            if payload.content is not None:
                yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class WaitForFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """WaitForFundsBehaviour"""

    matching_round: Type[AbstractRound] = WaitForFundsRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Agents wait for the funds to be received by the correct agent
            # Optionally, you can verify the receipt here using on-chain data
            # The content here doesn't matter
            payload = WaitForFundsPayload(sender=sender, content=True)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class ConsensusTendermintServiceRoundBehaviour(AbstractRoundBehaviour):
    """ConsensusTendermintServiceRoundBehaviour"""

    initial_behaviour_cls = WaitForFundsBehaviour
    abci_app_cls = ConsensusTendermintServiceAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        CheckResultsBehaviour,
        StartVotingBehaviour,
        TransferFundsBehaviour,
        WaitForFundsBehaviour
    ]
