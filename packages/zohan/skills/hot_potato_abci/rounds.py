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
from typing import Dict, FrozenSet, Optional, Set, Tuple
from collections import Counter
from packages.valory.skills.abstract_round_abci.base import (
    VotingRound,
)
from packages.zohan.skills.hot_potato_abci.rounds import Event, SynchronizedData

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    DegenerateRound,
    EventToTimeout,
    OnlyKeeperSendsRound,
    VotingRound,
)

from packages.zohan.skills.hot_potato_abci.payloads import (
    CheckResultsPayload,
    TransferFundsPayload,
    WaitForFundsPayload,
)


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

    CONSENSUS_REACHED = "consensus_reached" #I added this manually - do I need to change anything else - how does the application know to say this when consensus is reached?
    # Indicates that a consensus has been reached, which is the goal of the consensus process.

    NFT_TRANSFER_DETECTED = "nft_transfer_detected"


class SynchronizedData(BaseSynchronizedData):
    """Class to represent the synchronized data."""

    def __init__(self):
        """Initialize the synchronized data."""
        super().__init__()
        self.selected_receiver: Optional[str] = None
        self.last_transaction_hash: Optional[str] = None
        self.current_nft_owner: Optional[str] = None
        self.registered_agents: Set[str] = set()

    def update_selected_receiver(self, receiver: str) -> 'SynchronizedData':
        """Update the selected receiver."""
        self.selected_receiver = receiver
        return self

    def update_last_transaction_hash(self, transaction_hash: str) -> 'SynchronizedData':
        """Update the last transaction hash."""
        self.last_transaction_hash = transaction_hash
        return self

    def update_current_nft_owner(self, holder: str) -> 'SynchronizedData':
        """Update the current NFT owner."""
        self.current_nft_owner = holder
        return self

    def add_registered_agent(self, agent: str) -> 'SynchronizedData':
        """Add a registered agent."""
        self.registered_agents.add(agent)
        return self
    
    def nft_owner(self) -> Optional[str]:
        """Get the current NFT owner."""
        return self.current_nft_owner

    def update_vote(self, agent: str, vote: str) -> 'SynchronizedData':
        """Update the vote for an agent."""
        self.add_vote(agent, vote)
        return self
    # The "SynchronizedData" class is intended to maintain data that should be kept consistent across various parts of the Tendermint application. This kind of data often includes shared state or information that must be agreed upon by all parts of the system, like the current state of transactions or the consensus process.

class CheckResultsRound(VotingRound):
    """This round checks the voting results and determines the next NFT holder."""
    payload_class = CheckResultsPayload  # Assuming this payload includes the voting data
    payload_attribute = "receiver_candidate"  # Attribute will be the candidate each agent is voting for

    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """End the block and determine the next NFT holder."""

        votes = self.synchronized_data.get_votes()
        if not votes:
            return self.synchronized_data, Event.NO_MAJORITY

        # Count the votes for each agent
        vote_count = Counter(votes.values())
        if not vote_count:
            return self.synchronized_data, Event.NO_MAJORITY

        # Determine the majority vote
        receiver_candidate, _ = vote_count.most_common(1)[0]

        if receiver_candidate:
            # Found a candidate with majority votes, set as next receiver (or new NFT holder)
            self.synchronized_data.update_selected_receiver(receiver_candidate)
            self.context.logger.info(f"Agent {receiver_candidate} has been voted as the next NFT holder.")
            return self.synchronized_data, Event.CONSENSUS_REACHED
        else:
            # No clear majority; handle as required, for example, by starting a new round of voting
            return self.synchronized_data, Event.NO_MAJORITY

    def check_payload(self, payload: CheckResultsPayload) -> None:
        """Check payload."""
        # Update the payload verification logic to fit the new voting structure
        if not isinstance(payload.receiver_candidate, str):
            raise ValueError("Payload content does not contain a valid agent address.")

    def process_payload(self, payload: CheckResultsPayload) -> None:
        """Process the incoming payload to record the votes."""
        self.synchronized_data.add_vote(payload.sender, payload.receiver_candidate)

class StartVotingRound(VotingRound): #I've inputted this in rounds.py, but something is telling me the logic of the voting itself should be in behaviours.py - is this correct?
    """Round where agents vote for the next NFT holder."""

    async def async_act(self) -> None:
        """
        Initiate the voting round asynchronously.
        """
        # Get the current NFT owner from the SynchronizedData
        nft_owner = self.synchronized_data.nft_owner()
        # Prepare the list of candidates who can be voted for (all agents except the NFT owner)
        candidates = list(self.synchronized_data.registered_agents - {nft_owner})

        votes = {}
        # Iterate over all registered agents to collect their votes
        for agent in self.synchronized_data.registered_agents:
            if agent != nft_owner:  # The current NFT owner should not vote
                vote = self.collect_vote(agent, candidates)
                if vote:
                    votes[agent] = vote
                    self.context.logger.info(f"Agent {agent} voted for {vote}")
                else:
                    self.context.logger.info(f"Agent {agent} cannot vote; no candidates are available or ineligible to vote.")

        # Cast collected votes
        for agent, vote in votes.items():
            self.synchronized_data.update_vote(agent, vote)

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """
        Culminate the block by processing votes and deciding on the next steps.
        """
        # Retrieve the compiled votes from SynchronizedData
        votes = self.synchronized_data.get_votes()

        # Tally the votes and decide on the next NFT holder
        if votes:
            vote_count = Counter(votes.values())
            # Determine the next NFT holder (if a majority vote exists)
            next_holder, number_of_votes = vote_count.most_common(1)[0]
            if number_of_votes > len(votes) / 2:
                # A majority vote is detected, set the next NFT holder
                self.synchronized_data.update_selected_receiver(next_holder)
                return self.synchronized_data, Event.DONE
            else:
                # No majority vote found
                return self.synchronized_data, Event.NO_MAJORITY
        else:
            # No votes have been cast
            return self.synchronized_data, Event.NO_MAJORITY


class TransferNFTRound(OnlyKeeperSendsRound):
    """TransferNFTRound"""
    # This class handles the part of the consensus process where NFT ownership is transferred.

    payload_class = TransferFundsPayload  # This should likely be renamed or reused to contain NFT transfer confirmation data.
    payload_attribute = "transaction_payload"  # This attribute might need to be updated to fit NFT transfer confirmation.

    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """End the block by confirming the NFT transfer."""
        # Logic to check if the NFT transfer has been confirmed
        # This could involve checking a condition that determines if the round should end

        new_nft_owner = self.synchronized_data.get_selected_receiver()
        last_transaction_hash = self.synchronized_data.last_transaction_hash

        if new_nft_owner and last_transaction_hash:
            # Confirm the new NFT owner in SynchronizedData
            self.synchronized_data.update_current_nft_owner(new_nft_owner)
            
            # Log the confirmation of the NFT transfer and end the round
            self.context.logger.info(f"NFT has been successfully transferred to {new_nft_owner}.")
            return self.synchronized_data, Event.DONE
        else:
            # Handle the case where the NFT transfer is not confirmed or no new owner is selected
            self.context.logger.error("The NFT transfer has not been confirmed or no new owner was selected.")
            return self.synchronized_data, Event.ROUND_TIMEOUT


class WaitForNFTTransferRound(DegenerateRound):
    """WaitForNFTTransferRound"""
    # Represents the phase where agents wait for confirmation of NFT transfer
    # and check all agents have the minimum required xDAI for gas.

    payload_class = WaitForFundsPayload  # Update as needed to reflect the context
    payload_attribute = "confirmation"  # Confirmation of NFT ownership transfer
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """
        End the block by checking for NFT ownership transfer
        and ensuring all agents have a minimum balance for gas.
        """
        # Check for NFT owner from the synchronized_data and see if it matches the expected owner
        expected_nft_owner = self.synchronized_data.get_selected_receiver()

        # Implement fetch_current_nft_owner to interact with the smart contract
        current_nft_owner = self.fetch_current_nft_owner()  # Pseudo-code

        if expected_nft_owner != current_nft_owner:
            self.context.logger.warning("Waiting for NFT transfer confirmation.")
            return self.synchronized_data, Event.ROUND_TIMEOUT

        # Check if all agents have a minimum balance for gas
        for agent in self.synchronized_data.registered_agents:
            if self.get_agent_balance(agent) < 0.1:
                self.context.logger.error(f"Agent {agent} needs more xDAI for gas.")
                return self.synchronized_data, Event.ROUND_TIMEOUT

        # If the NFT is transferred and all agents have the minimum xDAI balance, progress to the next round
        self.synchronized_data.update_current_nft_owner(expected_nft_owner)
        self.context.logger.info(f"NFT is now held by {expected_nft_owner}.")
        return self.synchronized_data, Event.DONE


class ConsensusTendermintServiceAbciApp(AbciApp[Event]):
    """ConsensusTendermintServiceAbciApp"""
    # This class orchestrates the Tendermint consensus mechanism within the application.

    # Updating the initial round according to new context
    initial_round_cls: AppState = WaitForNFTTransferRound
    initial_states: Set[AppState] = {WaitForNFTTransferRound}

    # Transition function mapping needs to be updated based on new round names and logic
    transition_function: AbciAppTransitionFunction = {
        # The round that waits for NFT transfer to be confirmed
        WaitForNFTTransferRound: {
            Event.DONE: StartVotingRound,  # Proceed if NFT is transferred and minimum balance is satisfied
            Event.ROUND_TIMEOUT: WaitForNFTTransferRound  # Retry/wait if the round times out
        },
        # The round where agents vote for the next NFT holder
        StartVotingRound: {
            Event.DONE: CheckResultsRound,  # Move to checking results if voting is done
            Event.NO_MAJORITY: StartVotingRound,  # No majority, revote
            Event.ROUND_TIMEOUT: WaitForNFTTransferRound  # Timeout, go back to waiting for NFT transfer
        },
        # Round to determine the majority vote for the next NFT holder
        CheckResultsRound: {
            Event.DONE: TransferNFTRound,  # If majority found, proceed with NFT transfer
            Event.NO_MAJORITY: StartVotingRound  # No majority, revote
        },
        # Round to oversee the NFT transfer after a majority vote
        TransferNFTRound: {
            Event.DONE: WaitForNFTTransferRound,  # Once NFT transfer is confirmed, go back to waiting for the next transfer
            Event.ROUND_TIMEOUT: WaitForNFTTransferRound  # Timeout, retry/wait
        },
        
    }
    final_states: Set[AppState] = set()
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        # Pre-conditions for entering round states
        WaitForNFTTransferRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        # Post-conditions after exiting round states
    }