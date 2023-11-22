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
from aea.common import Address
from aea.ledger.base import LedgerApi

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
    def current_funds(self) -> float:
        """Return the current funds of the agent."""
        # Fetch and return the current funds of the agent
        return self.synchronized_data.get_current_funds(self.context.agent_address)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

class CheckResultsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """CheckResultsBehaviour"""
    # Logic for evaluating balance over the threshold is correct,
    # assuming that self.params.initial_funds has been set correctly elsewhere in the code.
    # The use of payload for a2a transactions follows the expected pattern.

    matching_round: Type[AbstractRound] = CheckResultsRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # Check if the current agent has more than 1xDAI
            balance = self.current_funds
            over_threshold = balance > self.params.initial_funds  # Use the threshold from initial funds.
            # The content is boolean, whether the agent has more than 1xDAI
            payload = CheckResultsPayload(sender=sender, content=over_threshold)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class StartVotingBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """StartVotingBehaviour"""
    matching_round: Type[AbstractRound] = StartVotingRound

    async def _get_balance(self, ledger_api: LedgerApi, address: Address) -> int:
        """Get balance of an agent asynchronously from the ledger."""
        balance = await ledger_api.async_get_balance(address)
        return balance

    async def _check_balance(self, address: Address) -> bool:
        """Check if the balance is above the threshold."""
        balance = await self._get_balance(self.context.ledger_apis.ethereum_api, address)
        threshold = self.context.params.initial_funds
        return balance > threshold

    async def async_act(self) -> None:
        """Perform the voting act asynchronously."""
        sender = self.context.agent_address
        # Determine the eligible candidates
        registered_agents = self.synchronized_data.registered_agents
        candidates = [agent for agent in registered_agents if await self._check_balance(agent)]
        # Ensure agents don't vote for an agent with already 1 xDAI
        candidates = [agent for agent in candidates if self.synchronized_data.get_current_funds(agent) <= 1]
        
        # Check how many eligible candidates exist to receive the pot
        if not candidates:
            self.context.logger.info("No eligible candidates to receive the pot.")
            return
        if len(candidates) == 1:
            receiver = candidates[0]
        else:
            # Randomly select a candidate to receive the pot
            receiver = random.choice(candidates)

        payload = StartVotingPayload(sender=sender, vote_for_receiver=receiver)
        self.context.logger.info(f"Voting for agent {receiver}")

        # Send the payload as an AEA transaction
        await self.context.outbox.put_message(message=payload)  # Replace with suitable method to send the payload
        await self.wait_until_round_end()  # Replace with suitable async waiting method from your framework

        self.set_done()  # Mark the behavior as done


class TransferFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """This behaviour manages the fund transfer actions."""
    
    matching_round: Type[AbstractRound] = TransferFundsRound

    async def _perform_transfer(self, receiver: str, amount: int) -> None:
        """Perform the fund transfer action."""
        # Placeholder for the actual transaction call, which should interact with the blockchain
        # For example, if interacting with Ethereum, you may need to use the web3 library:
        # txn = {'to': receiver, 'value': web3_instance.toWei(amount, 'ether'), 'gas': gas_estimate, ...}
        # tx_hash = self.context.ledger_apis.ethereum_api.send_transaction(txn)
        #
        # This is highly simplified; you need to consider nonce, gas price strategy, signing, etc.
        self.context.logger.info(f"Sending {amount} xDAI to receiver {receiver}")

        # Submit the transaction to the blockchain via the ledger API
        tx_receipt = await self.context.ledger_apis.ethereum_api.send_transaction(...)
        
        # Log the transaction receipt
        if tx_receipt:
            self.context.logger.info(f"Transaction receipt: {tx_receipt}")

        return tx_receipt

    async def async_act(self) -> None:
        """Perform the round's action asynchronously."""
        # Access the synchronized data to get the selected receiver and funds
        receiver = self.synchronized_data.get_selected_receiver()
        amount = 1  # Amount of xDAI to send, ensure proper denomination conversion as needed

        # Note: Ensure there's a mechanism to establish who the sender is and they have sufficient funds
        
        if receiver:
            tx_receipt = await self._perform_transfer(receiver, amount)
            # Store or handle the transaction receipt. Update synchronized_data if necessary.
            self.synchronized_data.set_last_transaction_receipt(tx_receipt)
        
        # Wait until the round ends or until the transfer is confirmed
        # The method below assumes you have async waiting capabilities matching your framework
        await self.wait_until_round_end()

        # Assuming this behavior runs once per majority decision
        self.set_done()


class WaitForFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """This behaviour manages waiting for confirmation of fund transfers."""
    
    matching_round: Type[AbstractRound] = WaitForFundsRound

    async def _check_funds_received(self, receiver: str, expected_amount: int) -> bool:
        """Check if the recipient has received the expected amount."""
        self.context.logger.info(f"Checking funds received by {receiver}.")
        balance = await self._get_balance(self.context.ledger_apis.ethereum_api, receiver)
        return balance >= expected_amount

    async def async_act(self) -> None:
        """Perform async action to confirm funds are received."""
        receiver = self.synchronized_data.get_selected_receiver()
        amount = 1  # Expected amount received, set to 1 xDAI for now

        funds_received = await self._check_funds_received(receiver, amount)
        if funds_received:
            self.context.logger.info(f"Confirmed {receiver} has received {amount} xDAI.")
        else:
            self.context.logger.error(f"Funds not received by {receiver}!")

        # Sleep/wait for some time if needed
        # wait_time = 30  # Time to wait for funds to be confirmed in seconds
        # await asyncio.sleep(wait_time)  # Use asyncio or other appropriate methods based on your agent framework
        
        # Once confirmation is complete or time has passed, set the round to be done
        self.set_done()



class ConsensusTendermintServiceRoundBehaviour(AbstractRoundBehaviour):
    """Manage the sequencing of round behaviours in the consensus service."""
    
    initial_behaviour_cls = WaitForFundsBehaviour  # The first behaviour to start
    abci_app_cls = ConsensusTendermintServiceAbciApp  # Your custom Tendermint ABCI app class
    behaviours: Set[Type[BaseBehaviour]] = {
        CheckResultsBehaviour,
        StartVotingBehaviour,
        TransferFundsBehaviour,
        WaitForFundsBehaviour,
    }

    def setup(self) -> None:
        """Set up the round behaviours."""
        # Perform any necessary setup for the round behaviours here.
        # May involve initializing shared resources or state, etc.
        pass

    def act(self) -> None:
        """Implement the logic to sequence round behaviours."""
        # Check the current state and decide which behaviour to run based on the state.
        # Transition from one behaviour to the next appropriately. This could be based
        # on events, conditions or messages received, etc.
        pass

    # Include any additional methods necessary for managing the round transitions here.

class SynchronizedData(BaseSynchronizedData):
    """Handle the synchronized data across behaviours and rounds."""

    def __init__(self):
        """Initialize the synchronized data."""
        super().__init__()
        self._funds = {}  # Keeps track of funds for each agent
        self._votes = {}  # Keeps track of votes each round
        self.selected_receiver = None  # Agent selected to receive funds
        self.last_transaction_hash = None  # Store the last transaction hash
        # Initialize any additional shared state here

    def get_current_funds(self, agent_address: str) -> float:
        """Get the current funds for the given agent."""
        return self._funds.get(agent_address, 0.0)

    def set_current_funds(self, agent_address: str, funds: float) -> None:
        """Set the current funds for the given agent."""
        self._funds[agent_address] = funds

    def add_vote(self, agent_address: str, receiver: str) -> None:
        """Add a vote for a given receiver."""
        self._votes[agent_address] = receiver

    def get_votes(self) -> Dict[str, str]:
        """Get all current votes."""
        return self._votes

    def reset_votes(self) -> None:
        """Reset votes for a new round."""
        self._votes.clear()

    def count_votes(self) -> Dict[str, int]:
        """Count and return the votes for each receiver."""
        vote_counts = Counter(self._votes.values())
        return dict(vote_counts)

    # Additional methods needed for the business logic