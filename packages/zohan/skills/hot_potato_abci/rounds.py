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

import random
import time
from collections import Counter
from enum import Enum
from typing import Dict, FrozenSet, Generator, List, Optional, Set, Tuple

import requests
from aea.context.base import Context
from aea.contracts.base import Contract
from aea.exceptions import AEAEnforceError
from aea.ledger.ethereum import EthereumApi
from aea.protocols.base import Message
from aea.skills.behaviours import TickerBehaviour

from packages.valory.connections.ledger.base import LedgerApiMessage
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
from packages.valory.skills.hot_potato_abci.rounds import Event, SynchronizedData


class Event(Enum):
    """ConsensusTendermintServiceAbciApp Events"""

    # This "Event" class is a special kind of class in Python that represents a set of named constant values. Each item represents a possible event that might occur in the ConsensusTendermintServiceAbciApp, and they are used to signal different types of occurrences within the app.

    ROUND_TIMEOUT = "round_timeout"
    # Represents an event that occurs when a round in the consensus process takes too long and times out.

    DONE = "done"
    # Indicates that an operation or a series of operations has completed successfully.

    NO_MAJORITY = "no_majority"
    # Signifies that a vote or decision did not reach a majority agreement.

    NEW_BALANCE_DETECTED = "new_balance_detected"
    # Used to flag that a change in an agent's balance has been observed, which could be due to funds being received or transferred.


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    # The "SynchronizedData" class is intended to maintain data that should be kept consistent across various parts of the Tendermint application. This kind of data often includes shared state or information that must be agreed upon by all parts of the system, like the current state of transactions or the consensus process.


class CheckResultsRound(VotingRound):
    """CheckResultsRound"""

    # This class represents a specific stage in the voting process where the results are checked.

    payload_class = CheckResultsPayload
    # Defines what type of data is expected to be handled during this round. It will work with 'CheckResultsPayload', which is likely a data structure storing whether an agent's balance is above a threshold.

    payload_attribute = (
        "over_threshold"  # Payload attribute updated as per the actual content
    )
    # Tells the system which particular piece of information from the payload it needs to focus on, in this case, whether or not an agent's balance is over a certain threshold.

    synchronized_data_class = SynchronizedData
    # Specifies the class that will be used to manage and access synchronized data during this round.

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        # This method is called at the end of a block of operations, which can be thought of like a 'round' within the voting process.

        over_threshold_votes = self.synchronized_data.get_votes_with_condition(True)
        # Retrieves votes indicating an agent has more funds than the threshold.

        if len(over_threshold_votes) == 0:
            # If no agents have a balance over the threshold, it might indicate that voting should either start over or stop completely, depending on the established rules (business logic).

            return self.synchronized_data, Event.NO_MAJORITY
            # Returns the current state of synchronized data along with an event signaling that no majority was reached.

        if len(over_threshold_votes) > 1:
            # If there are multiple agents with balances over the threshold, this is an unexpected situation and should be handled according to specific business rules.

            raise Exception("Multiple agents have a balance over the threshold.")
            # Raises an error because this scenario may indicate a problem with the business logic or application state.

        majority_vote = over_threshold_votes.pop()
        self.synchronized_data.selected_receiver = majority_vote
        # Sets the agent that will receive funds, which is the only one with a balance over the threshold.

        return self.synchronized_data, Event.DONE
        # Returns updated synchronized data and a 'done' event to indicate this round of the process is complete.

    def check_payload(self, payload: CheckResultsPayload) -> None:
        """Check payload."""
        # Ensures that the incoming payload (the data package) is correctly formatted. It's expected to be a boolean of whether the agent's balance is over 1xDAI.

        if not isinstance(payload.content, bool):
            raise ValueError(
                "Payload content is not a boolean indicating balance threshold status."
            )
            # If the payload content isn't a true/false value, raises a ValueError as that's not expected.

    def process_payload(self, payload: CheckResultsPayload) -> None:
        """Process payload."""
        # This method takes the incoming payload and uses it to update the synchronized data with information on who has funds above or below the threshold.

        if payload.over_threshold:
            self.synchronized_data.add_vote(payload.sender, True)
        else:
            self.synchronized_data.add_vote(payload.sender, False)
        # Adds a 'vote' to the synchronized data based on whether the agent's balance was over the threshold.

    # The remaining methods, `is_valid_agent_identifier` and `get_balance_from_rpc`, are placeholders for logic that would validate the format of agent identifiers and query a blockchain over a network for an agent's balance, respectively. They illustrate how such a system might interact with an actual blockchain network to retrieve data, but they're not fully implemented here and would require more details based on a specific blockchain.


class StartVotingRound(VotingRound):
    """StartVotingRound"""

    # This class represents one of the early stages in the voting process within a consensus mechanism.

    # The attributes below are assumed to be inherited from VotingRound, which would be a base class providing common structure and behavior for different types of voting rounds:

    payload_class = StartVotingPayload
    # This variable indicates what type of data (payload) the round will handle, specifically a 'StartVotingPayload', which likely contains information necessary for initiating the voting process.

    payload_attribute = "vote_for_receiver"  # Payload attribute
    # This specifies which part of the payload data should be focused on during this round, here it's the 'vote_for_receiver' attribute, which probably identifies the agent receiving a vote.

    synchronized_data_class = SynchronizedData
    # Points to the class that holds data shared and synchronized across different components while this round is occurring.

    ledger_api = EthereumApi(...)
    # Introduces a way to interact with the Ethereum blockchain (or similar ledger technology). The actual setup would depend on your application's context and needs.

    async def _get_balance(self, agent: str) -> Generator[None, None, Optional[int]]:
        """Get the balance of the specified agent asynchronously using ledger API."""
        # An asynchronous function for retrieving an agent's balance from a ledger, using the `ledger_api` defined earlier.

        balance = await self.ledger_api.get_balance(agent)
        # The balance lookup happens asynchronously and waits for the ledger's response.

        return balance

    async def _check_balance(self, agent: str) -> bool:
        """Check if the given agent's balance is over the threshold."""
        # Another asynchronous function that checks if an agent's balance exceeds a defined amount (threshold).

        balance = None
        while balance is None:
            balance = await self._get_balance(agent)
        # It continuously attempts to retrieve the balance until successful.

        threshold = 1  # Replace 1 with the actual threshold value in xDAI equivalent.
        # The 'threshold' is the balance limit we're interested in checking against.

        return balance > threshold

    async def async_act(self) -> None:
        """Perform the round's action."""
        # The main asynchronous action of this round, where the voting logic of your skill is implemented.

        candidates = []  # List of candidate agents
        votes = {}  # Dictionary to hold votes
        # Prepares lists to track candidates and votes during the round.

        for agent in self.synchronized_data.registered_agents:
            if agent != self.synchronized_data.current_holder:
                can_vote = await self._check_balance(agent)
                if can_vote:
                    vote = random.choice(candidates)
                    votes[agent] = vote
        # For each registered agent, if they're not currently holding the token (or subject of the vote), and if their balance allows them to vote, they cast a vote for a randomly chosen candidate.

        for voter, vote in votes.items():
            payload = StartVotingPayload(sender=voter, vote_for_receiver=vote)
            self.context.logger.info(f"Agent {voter} voted for {vote}")
        # Each vote is recorded in a payload and information about it is logged.

        # Wait for the end of the round
        # Your framework would likely provide a method to wait for the end of the voting round, which would go here.

    def check_payload(self, payload: StartVotingPayload) -> None:
        """
        Check the payload to ensure it is a valid vote.
        """
        # Retrieves the balance of the agent that is voted for.
        receiver_balance = self.synchronized_data.get_current_funds(
            payload.vote_for_receiver
        )

        # Considering the initial 0.1 xDAI for gas, balance should not exceed 1.1 xDAI.
        balance_threshold = 1.0 + 0.1  # Adjust the threshold based on your game rules.
        balance_sufficient = receiver_balance <= balance_threshold

        # Confirms the validity of the data received.
        if not balance_sufficient:
            raise ValueError(
                f"Agent identified in 'vote_for_receiver' ({payload.vote_for_receiver}) holds more than the expected balance limit."
            )

    def process_payload(self, payload: StartVotingPayload) -> None:
        """
        Process payload to record the vote.
        """
        # Records the vote by updating the synchronized data to reflect the newly received vote information.
        self.synchronized_data.update_vote(payload.sender, payload.vote_for_receiver)


class TransferFundsRound(OnlyKeeperSendsRound):
    """TransferFundsRound"""

    # This class handles the part of the consensus process where funds are actually transferred.

    payload_class = TransferFundsPayload
    # Specifies the type of data this round will handle—a 'TransferFundsPayload', which would contain the information needed to execute a fund transfer.

    payload_attribute = (
        "transaction_payload"  # Updated to represent the DAI transfer payload
    )
    # Indicates the specific attribute of the payload that's important for this round. In this case, it's the details of the transaction that will transfer funds.

    synchronized_data_class = SynchronizedData
    # Identifies the class that's responsible for storing and managing data that needs to be kept in sync among different components during this round.

    def perform_transfer(self, receiver: str) -> str:
        # A method intended to actually carry out the fund transfer.
        # It's a placeholder here, and the real implementation would involve interacting with the blockchain and returning a unique identifier for the transaction ('transaction_hash').

        transaction_hash = "dummy_tx_hash"  # Placeholder for a real transaction hash that you would get from the blockchain.
        return transaction_hash

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        # Called at the end of the round, assuming all actions have been performed and it's time to wrap up and prepare for the next step.

        receiver = self.synchronized_data.get_selected_receiver()
        # Gets the recipient who has been chosen to receive the funds.

        if receiver:
            transaction_hash = self.perform_transfer(receiver)
            # Executes the fund transfer to the chosen recipient and gets the transaction hash as a receipt.

            self.synchronized_data.last_transaction_hash = transaction_hash
            # Stores the transaction hash in the synchronized data for future reference.

            self.synchronized_data.set_current_funds(
                receiver, 1
            )  # Assumes the receiver now has exactly 1 xDAI after the transfer.
            # Updates the synchronized data to reflect the new balance of the receiver.

            return self.synchronized_data, Event.DONE
            # Returns the updated synchronized data and an event signifying that the round is complete.

        else:
            raise Exception("No receiver selected for transfer.")
            # If no recipient has been set, it raises an error because the transfer cannot proceed.

    def check_payload(self, payload: TransferFundsPayload) -> None:  # do i need this?
        """Check payload."""
        # This method would validate the data received in the payload to ensure it's correct before processing.
        # It isn't implemented in this placeholder and raises an error, indicating that you will need to implement it as needed.

        raise NotImplementedError

    def process_payload(self, payload: TransferFundsPayload) -> None:  # do i need this?
        """Process payload."""
        # This would be the method to handle and act upon the received payload data, updating any necessary state or performing actions based on the payload.
        # Like checking, it's not implemented here and requires proper implementation if needed.

        raise NotImplementedError


class WaitForFundsRound(DegenerateRound):
    """WaitForFundsRound"""

    # This class represents a phase in the consensus process where agents (participants in the network) wait for confirmation that funds have been successfully transferred.

    payload_class = WaitForFundsPayload
    # Indicates the type of data this round will handle—a 'WaitForFundsPayload'. The payload should carry information regarding fund transfer confirmation.

    payload_attribute = "confirmation"  # Assume this is a simple boolean confirmation
    # Points to a specific piece of information in the payload that's important for this round, which would be a simple true/false (boolean) value indicating whether the funds were received.

    synchronized_data_class = SynchronizedData
    # Specifies that this round will rely on the 'SynchronizedData' class for its shared, consistent data needs.

    # During this round, agents are expected to wait for the blockchain network to confirm that a fund transfer has occurred successfully, typically verified by ensuring that the intended recipient's balance has increased.

    def check_balance(self, expected_balances):
        # A method to check the confirmed balances of agents via a blockchain node. The actual implementation would involve a query to the blockchain network.

        time.sleep(
            30
        )  # The system waits for 30 seconds to give the network time to process the transaction and sync.
        return True  # Assuming the balance check was successful, we return true. This is a simplification for illustration.

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        # Called at the end of the wait round to bring it to a close.

        expected_balances = {
            agent: amount > 1
            for agent, amount in self.synchronized_data.agent_amounts.items()
        }
        # Sets up what balances are expected for each agent (more than 1 xDAI, in this scenario).

        funds_received = self.check_balance(expected_balances)
        # Checks the actual balances against the expected ones.

        if funds_received:
            return self.synchronized_data, Event.NEW_BALANCE_DETECTED
            # If the funds have been received as expected, returns the event 'NEW_BALANCE_DETECTED' indicating that the process can move forward.

        else:
            return self.synchronized_data, Event.ROUND_TIMEOUT
            # If the funds were not received, returns the event 'ROUND_TIMEOUT' to signal that the round did not complete successfully.

    def check_payload(self, payload: WaitForFundsPayload) -> None:  # do i need this?
        """Check payload."""
        # This would be a method to verify the payload data – that it has the necessary and correctly formatted information.

        raise NotImplementedError
        # Not yet implemented, and would need to be properly developed to match the payload verification needs of this particular round.

    def process_payload(self, payload: WaitForFundsPayload) -> None:  # do i need this?
        """Process payload."""
        # This would be the method to process the payload data, to act upon it and update the state as necessary for the progress of the round.

        raise NotImplementedError
        # Like 'check_payload', this one is also not implemented and requires appropriate logic for processing the payload.


class ConsensusTendermintServiceAbciApp(AbciApp[Event]):
    """ConsensusTendermintServiceAbciApp"""

    # This class is the main application that orchestrates the different stages (rounds) of the consensus process using Tendermint, which is a blockchain consensus mechanism.

    initial_round_cls: AppState = WaitForFundsRound
    # Specifies the first stage in the consensus process, which is where the participants wait for confirmation of fund transfers.

    initial_states: Set[AppState] = {WaitForFundsRound}
    # Sets up the initial state or phase of the application, which is the 'WaitForFundsRound'.

    transition_function: AbciAppTransitionFunction = {
        # This is a map that defines how the application transitions from one round to another based on different events.
        WaitForFundsRound: {Event.DONE: StartVotingRound},
        # If the 'WaitForFundsRound' completes successfully ('DONE'), then the next stage is 'StartVotingRound'.
        StartVotingRound: {
            Event.DONE: CheckResultsRound,
            Event.NO_MAJORITY: StartVotingRound,
            Event.ROUND_TIMEOUT: WaitForFundsRound,
        },
        # Defines what happens after 'StartVotingRound', such as moving to the 'CheckResultsRound', starting the voting over, or reverting to waiting for funds, depending on the event.
        CheckResultsRound: {
            Event.DONE: TransferFundsRound,
            Event.NO_MAJORITY: StartVotingRound,
        },
        # After checking results ('CheckResultsRound'), if successful ('DONE'), proceed to transfer funds ('TransferFundsRound'). If no clear decision is made ('NO_MAJORITY'), start voting again.
        TransferFundsRound: {
            Event.DONE: WaitForFundsRound,
            Event.ROUND_TIMEOUT: WaitForFundsRound,
        }
        # Once funds are transferred, either go back to waiting for funds ('WaitForFundsRound') or stay in the same round if there's a timeout.
    }
    final_states: Set[AppState] = set()
    # Defines any final states for the application; here, it's an empty set, meaning no specific final states are defined.

    event_to_timeout: EventToTimeout = {}
    # Maps events to timeouts, but it's empty in this structure, meaning there's no default timeout behavior provided.

    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    # Determines which state keys should be kept across different phases or rounds. Currently, no keys are specified.

    db_pre_conditions: Dict[AppState, Set[str]] = {
        WaitForFundsRound: [],
    }
    # Specifies any conditions that must be met before entering a particular state, such as `WaitForFundsRound`. In this case, no pre-conditions are required.

    db_post_conditions: Dict[AppState, Set[str]] = {
        # Similar to pre-conditions, this defines conditions that should be met after exiting a state. It's empty here, indicating no specific post-conditions.
    }
