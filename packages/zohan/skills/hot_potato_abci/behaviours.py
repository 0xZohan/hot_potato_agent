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

import random
from abc import ABC
from collections import Counter
from typing import Counter, Dict, Generator, Set, Type, cast, Optional

from aea.common import Address
from aea.ledger.base import LedgerApi
from aea.skills.base import BaseSynchronizedData

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.zohan.skills.hot_potato_abci.models import Params
from packages.zohan.skills.hot_potato_abci.rounds import (
    CheckResultsPayload,
    CheckResultsRound,
    ConsensusTendermintServiceAbciApp,
    StartVotingPayload,
    StartVotingRound,
    SynchronizedData,
    TransferFundsPayload,
    TransferFundsRound,
    WaitForFundsPayload,
    WaitForFundsRound,
)


class ConsensusTendermintServiceBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the hot_potato skill."""

    # This class acts as a foundation for other behaviors in a skill called 'hot_potato', which likely involves passing on an object (like a 'hot potato') under certain conditions.

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        # Defines a special read-only property that provides access to the synchronized data held by the system.

        return cast(SynchronizedData, super().synchronized_data)
        # This returns the synchronized data, confirming that it is the correct type for use in this particular skill context.

    @property
    def current_funds(self) -> float:
        """Return the current funds of the agent."""
        # Another special read-only property that gives the current balance of xDAI for the agent.

        # The following line retrieves and returns the funds that the agent has.
        return self.synchronized_data.get_current_funds(self.context.agent_address)
        # It gets the agent's address from the context (the environment that the agent operates in) and requests the agent's balance from the synchronized data.

    @property
    def params(self) -> Params:
        """Return the params."""
        # This property gives access to various parameters that can be used by the behavior (like settings or configurations).

        return cast(Params, super().params)
        # Returns the parameters, ensuring that they are of the correct type for use within the agent's behaviors.


class CheckResultsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """CheckResultsBehaviour"""

    # This line defines a new class called `CheckResultsBehaviour` that is based on a template for consensus services using Tendermint.

    matching_round: Type[AbstractRound] = CheckResultsRound
    # This line sets up the type of 'round' that this behavior is associated with. A 'round' is a phase in the consensus process, and 'CheckResultsRound' is a specific phase where checking of results happens.

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        # Here, we are defining a function that will be performed by the behavior.

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            # This creates a special context that measures how long the following code takes to run. It also retrieves the unique address of the agent (like an account number) and stores it in 'sender'.

            balance = self.current_funds
            # This line checks the current 'balance' of the agent.

            over_threshold = balance > self.params.initial_funds
            # Here, we determine whether the agent's balance is more than a specified 'threshold' amount, which was set earlier in the program (in aea-config).

            payload = CheckResultsPayload(sender=sender, content=over_threshold)
            # A 'payload' is a packet of data. It's created here to contain the sender's address and a true/false value indicating whether the balance is over the threshold.

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            # This line sends the payload we created in the previous step to other participants in a process known as 'agent-to-agent' (a2a) transaction while recording how long it takes.

            yield from self.wait_until_round_end()
            # This tells the agent to wait until the current phase or 'round' of the consensus process is finished.

        self.set_done()
        # Finally, this line marks the behavior as completed.


class StartVotingBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """StartVotingBehaviour"""

    # This line defines a new class for a behavior that starts the voting process using the Tendermint consensus method.

    matching_round: Type[AbstractRound] = StartVotingRound
    # Specifies which part of the consensus process this behavior is associated with, in this case, the 'StartVotingRound'.

    async def _get_balance(self, ledger_api: LedgerApi, address: Address) -> int:
        """Get balance of an agent asynchronously from the ledger."""
        # This function retrieves the xDAI balance of an agent from the blockchain ledger asynchronously, without holding up other processes.

        balance = await ledger_api.async_get_balance(address)
        # Calls the function to get the balance and waits for it to respond.

        return balance
        # The function then returns the numerical balance value.

    async def _check_balance(self, address: Address) -> bool:
        """Check if the balance is above the threshold."""
        # This function checks if the agent's balance is above a certain threshold amount.

        balance = await self._get_balance(
            self.context.ledger_apis.ethereum_api, address
        )
        # Retrieves the balance of the agent using Ethereum's ledger API.

        threshold = self.context.params.initial_funds
        # Retrieves the threshold value from the context parameters.

        return balance > threshold
        # Returns True if the balance is higher than the threshold, otherwise False.

    async def async_act(self) -> None:
        """Perform the voting act asynchronously."""
        # This function handles the voting action and allows it to be performed in the background.

        sender = self.context.agent_address
        # Gets the unique identifier of the current agent, which will act as the sender in the voting.

        registered_agents = self.synchronized_data.registered_agents
        # Retrieves a list of all agents that have registered for voting.

        candidates = [
            agent for agent in registered_agents if await self._check_balance(agent)
        ]
        # Filters out agents who have a balance higher than the threshold to create a list of eligible voting candidates.

        candidates = [
            agent
            for agent in candidates
            if self.synchronized_data.get_current_funds(agent) <= 1
        ]  # I think i need to make this contract (token id) specific
        # Removes candidates that already have more than 1 unit of the xDAI, narrowing down to those eligible to receive a vote. - maybe these needs to be changed to 10^18? (hexadecimal format)

        if not candidates:
            self.context.logger.info(
                "No eligible candidates to receive the hot potato."
            )
            return
        # If there are no eligible candidates, log an informative message and end the execution of this function.

        if len(candidates) == 1:
            receiver = candidates[0]
        # If only one candidate is eligible, they automatically become the receiver of the vote.

        else:
            receiver = random.choice(candidates)
            # If multiple candidates are eligible, randomly select one as the receiver.

        payload = StartVotingPayload(sender=sender, vote_for_receiver=receiver)
        # Creates a data package ('payload') containing the sender's info and the chosen voting receiver.

        self.context.logger.info(f"Voting for agent {receiver}")
        # Logs which agent is being voted for.

        await self.context.outbox.put_message(message=payload)
        # Sends the created payload to the network for processing in the voting.

        await self.wait_until_round_end()
        # Waits for the current voting round to conclude before proceeding.

        self.set_done()
        # Marks this voting behavior as completed.

class TransferFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """This behaviour manages the fund transfer actions based on voting results."""

    matching_round: Type[AbstractRound] = TransferFundsRound

    async def _perform_transfer(self, sender: str, receiver: str, amount: int) -> Optional[str]:
        """Perform the fund transfer action."""
        self.context.logger.info(f"Sending {amount} xDAI from {sender} to receiver {receiver}")
        # Perform the fund transfer from sender to receiver.
        tx_receipt = await self.context.ledger_apis.ethereum_api.send_transaction(sender, receiver, amount)
        
        # Log the transaction success or failure.
        if tx_receipt:
            self.context.logger.info(f"Transaction successful with receipt: {tx_receipt}")
            return tx_receipt
        else:
            self.context.logger.error("Transaction failed for receiver {receiver}")
            return None

    async def async_act(self) -> None:
        """Perform the round's action asynchronously."""
        # Retrieve the agent who holds the hot potato from the previous round.
        hot_potato_holder = self.synchronized_data.get_hot_potato_holder()
        if hot_potato_holder is None:
            self.context.logger.error("No agent identified to transfer the hot potato.")
            return
        
        # Tally votes to find the agent with the most votes to receive the hot potato.
        vote_counts: Dict[str, int] = self.synchronized_data.count_votes()
        if not vote_counts:
            self.context.logger.error("No votes were cast. Cannot transfer funds.")
            return

        # Find out which agent received the most votes.
        winning_agent, _ = max(vote_counts.items(), key=lambda item: item[1])
        
        # Perform the transfer from the hot potato holder to the winning agent.
        amount_to_transfer = 1  # The amount to be transferred (1 xDAI), adjust as needed.
        tx_receipt = await self._perform_transfer(hot_potato_holder, winning_agent, amount_to_transfer)
        
        # Update synchronized data with the transaction receipt if the transfer was successful.
        if tx_receipt is not None:
            self.synchronized_data.set_last_transaction_receipt(tx_receipt)
            self.context.logger.info(f"Transferred {amount_to_transfer} xDAI to agent {winning_agent}.")
        else:
            self.context.logger.error("The transfer could not be performed.")

        await self.wait_for_round_end()
        self.set_done()

    async def wait_for_round_end(self) -> None:
        """Wait for the round to end."""
        # Implement the waiting logic here. This might involve waiting for a signal or simply delaying.
        pass

    def set_done(self) -> None:
        """Mark this behaviour as done."""
        # Set the behavior state to finished, and potentially trigger the next action or behavior.
        pass


class WaitForFundsBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """This behaviour manages waiting for confirmation of fund transfers."""

    # This class handles the process of checking whether a transfer of funds to a receiver has been completed.

    matching_round: Type[AbstractRound] = WaitForFundsRound
    # It indicates that this behavior corresponds to a specific part of the process called 'WaitForFundsRound'.

    async def _check_funds_received(self, receiver: str, expected_amount: int) -> bool:
        """Check if the recipient has received the expected amount."""
        # This is an internal method that checks if the receiver has gotten the amount of money that was supposed to be sent.

        self.context.logger.info(f"Checking funds received by {receiver}.")
        # Logs a message that a check is being made for the funds received by the receiver.

        balance = await self._get_balance(
            self.context.ledger_apis.ethereum_api, receiver
        )
        # Calls a function to get the receiver's current balance from the blockchain ledger and waits for the response.

        return balance >= expected_amount
        # Returns True if the balance is equal to or greater than the expected amount, indicating that the funds were received. - ensure this is basically a balance > 1 does this need to be in hexidecimal format? (10^18)

    async def async_act(self) -> None:
        """Perform async action to confirm funds are received."""
        # The main method to be executed, which manages the checking of whether the funds have been received in a non-blocking way.

        receiver = self.synchronized_data.get_selected_receiver()
        # Finds out who was supposed to receive the funds according to previously synchronized data.

        amount = 1  # Expected amount received, set to 1 xDAI for now - again, does this need to be in hexidecimal format? (10^18)
        # The amount expected to have been received, here it's set to a fixed value of 1 xDAI.

        funds_received = await self._check_funds_received(receiver, amount)
        # Calls the internal method to check if the funds were received and waits for confirmation.

        if funds_received:
            self.context.logger.info(
                f"Confirmed {receiver} has received {amount} xDAI."
            )
            # If the funds were received, logs a confirmation message.

        else:
            self.context.logger.error(f"Funds not received by {receiver}!")
            # Otherwise, logs an error message saying the funds were not received.

        # If there was a need to wait a certain amount of time before moving on, the code would pause here.
        # wait_time = 30  # Represents how long you would wait in seconds.
        # await asyncio.sleep(wait_time)  # This line would make the program wait for that specified time.

        self.set_done()
        # Marks this behavior as finished, meaning the check for funds receipt is complete.


class ConsensusTendermintServiceRoundBehaviour(AbstractRoundBehaviour):
    """Manage the sequencing of round behaviours in the consensus service."""

    # This class is responsible for managing the order in which different behaviors occur as part of the consensus process using Tendermint, a blockchain consensus algorithm.

    initial_behaviour_cls = WaitForFundsBehaviour  # The first behaviour to start
    # Specifies that the first action in the sequence is to wait for confirmation of fund transfers.

    abci_app_cls = (
        ConsensusTendermintServiceAbciApp  # Your custom Tendermint ABCI app class
    )
    # Identifies the specific application class that interfaces with the Tendermint consensus, meaning it's the part that actually talks to the blockchain.

    behaviours: Set[Type[BaseBehaviour]] = {
        CheckResultsBehaviour,
        StartVotingBehaviour,
        TransferFundsBehaviour,
        WaitForFundsBehaviour,
    }
    # This is a list of all the different behaviors that this class manages. Each behavior represents a specific task or action that takes place during the consensus process.

    def setup(self) -> None:
        """Set up the round behaviours."""
        # This function is used to prepare everything that's necessary before the behaviors start running. It could be used to initiate resources or set up initial state.

        pass  # Currently, it does nothing and acts as a placeholder.

    def act(self) -> None:
        """Implement the logic to sequence round behaviours."""
        # The main function that determines the order of operations for the behaviors. It decides which behavior to execute next based on the current state, events that have happened, or messages received.

        pass  # Like the setup function, it currently does nothing and serves as a placeholder for actual sequencing logic.

    # Additional helper methods for managing the behavior transitions can be added to this class, following the pattern of setup and act methods.


class SynchronizedData(BaseSynchronizedData):
    """Handle the synchronized data across behaviours and rounds."""

    # This class is designed to keep certain data in sync across different parts of the program. This helps ensure that different components are working with the same information, which is crucial in a process that requires consensus.

    def __init__(self):
        """Initialize the synchronized data."""
        super().__init__()
        # This is a constructor method that sets up the class. It calls an initialization method from its parent class to make sure it has all the necessary underlying functionality.

        self._funds = {}  # Keeps track of funds for each agent
        # This creates an empty dictionary to store how much digital currency each agent (participant) has.

        self._votes = {}  # Keeps track of votes each round
        # This sets up an empty dictionary to record the votes that are made during a round of consensus.

        self.selected_receiver = None  # Agent selected to receive funds
        # Here is a placeholder for storing the identifier of the agent who has been chosen to receive funds after a round of voting.

        self.last_transaction_hash = None  # Store the last transaction hash
        # This holds the identifier for the last fund transfer transaction that occurred. It serves as a reference to confirm that a transaction has been completed.

    def get_current_funds(self, agent_address: str) -> float:
        """Get the current funds for the given agent."""
        # This method retrieves the amount of funds available to a specific agent.

        return self._funds.get(agent_address, 0.0)
        # It looks up the agent's address in the funds dictionary and returns the balance. If the agent isn't listed, it defaults to 0.0.

    def set_current_funds(self, agent_address: str, funds: float) -> None:
        """Set the current funds for the given agent."""
        # This method updates the funds for a particular agent.

        self._funds[agent_address] = funds
        # It assigns the new funds value to the agent's entry in the funds dictionary.

    def add_vote(self, agent_address: str, receiver: str) -> None:
        """Add a vote for a given receiver."""
        # Adds a record of a vote from an agent for a particular receiver.

        self._votes[agent_address] = receiver
        # It stores the receiver chosen by an agent inside the votes dictionary.

    def get_votes(self) -> Dict[str, str]:
        """Get all current votes."""
        # Retrieves all the recorded votes.

        return self._votes
        # Simply returns the dictionary containing the votes.

    def reset_votes(self) -> None:
        """Reset votes for a new round."""
        # Clears out the votes in preparation for a new round of voting.

        self._votes.clear()
        # Empties the votes dictionary so it can be filled with fresh data in the next round.

    def count_votes(self) -> Dict[str, int]:
        """Count and return the votes for each receiver."""
        # Tallies up the votes and shows how many each receiver got.

        vote_counts = Counter(self._votes.values())
        # Creates a count of all the votes from the votes dictionary.

        return dict(vote_counts)
        # Turns the count into a dictionary where each receiver's address is a key and their vote total is the value.
