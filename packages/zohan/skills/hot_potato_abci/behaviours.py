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
from typing import  Dict, Set, Type, cast
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from aea.contracts.base import ContractApiDialogues
from aea.protocols.base import Message
from aea.crypto.ledger_apis import LedgerApi
from packages.valory.skills.abstract_round_abci.behaviours import ABCIRoundBehaviour
from packages.zohan.skills.hot_potato_abci.rounds import (
    CheckResultsRound,
)
from aea.contracts.base import ContractApiMessage, ContractApiDialogues
from aea.common import Address

from aea.common import Address
from aea.skills.behaviours import TickerBehaviour
from aea_ledger_ethereum import EthereumApi
from aea.skills.base import BaseSynchronizedData


from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.zohan.skills.hot_potato_abci.models import Params
from packages.zohan.skills.hot_potato_abci.rounds import (
    CheckResultsRound,
    ConsensusTendermintServiceAbciApp,
    StartVotingRound,
    SynchronizedData,
    TransferFundsRound,
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
    def nft_owner(self) -> Address:
        """Return the current owner of the NFT."""
        # Gets the current NFT owner from the synchronized data
        return self.synchronized_data.nft_owner

    @property
    def params(self) -> Params:
        """Return the params."""
        # This property gives access to various parameters that can be used by the behavior (like settings or configurations).

        return cast(Params, super().params)
        # Returns the parameters, ensuring that they are of the correct type for use within the agent's behaviors.


class CheckResultsBehaviour(ABCIRoundBehaviour):
    """CheckResultsBehaviour that checks whether the agent holds an NFT."""

    matching_round = CheckResultsRound

    async def async_act(self) -> None:
        """Perform the balance check asynchronously."""
        # Ensure this behaviour runs only in the matching round
        if not isinstance(self.context.round_sequence.current_round, self.matching_round):
            return

        # Retrieve relevant data
        sender = self.context.agent_address
        ledger_id = self.context.default_ledger_id
        contract_id = str(self.params.nft_contract_id)
        token_id = str(self.params.nft_token_id)

        # Prepare the API call to get the balance
        kwargs = {"address": sender}
        contract_api_call = self._prepare_api_call(ledger_id, contract_id, token_id, "get_balance", kwargs)

        # Send the API call to the outbox (non-blocking)
        self.context.outbox.put_message(message=contract_api_call)
        
        # Indicate the behavior is done for this step; response handling will occur elsewhere
        self.set_done()

    def _prepare_api_call(self, ledger_id: str, contract_id: str, token_id: str, callable: str, kwargs: dict) -> Message:
        """
        Prepare the API call for the contract.
        """
        # Get the contract API dialogues
        contract_api_dialogues: ContractApiDialogues = self.context.contract_api_dialogues
        
        # Create the contract API request
        request = ContractApiMessage(
            performative=ContractApiMessage.Performative.GET_STATE,
            dialogue_reference=contract_api_dialogues.new_self_initiated_dialogue_reference(),
            ledger_id=ledger_id,
            contract_id=contract_id,
            token_id=token_id,
            callable=callable,
            kwargs=ContractApiMessage.Kwargs(kwargs)
        )

        # Create the contract API dialogue
        contract_api_dialogue = contract_api_dialogues.create_with_message(request)

        return contract_api_dialogue.last_incoming_message


class StartVotingBehaviour(ConsensusTendermintServiceBaseBehaviour):
    """StartVotingBehaviour which initiates the voting process."""

    matching_round: Type[AbstractRound] = StartVotingRound

    async def _get_balance(self, ledger_api: LedgerApi, address: Address) -> None:
        """Prepare the API call for getting balance and send to the outbox."""
        contract_api_dialogues: ContractApiDialogues = self.context.contract_api_dialogues
        kwargs = {"address": address}
        request = ContractApiMessage.performative(
            performative=ContractApiMessage.Performative.GET_STATE,
            dialogue_reference=contract_api_dialogues.new_self_initiated_dialogue_reference(),
            ledger_id=ledger_api.identifier,
            contract_id=str(self.params.nft_contract_id),
            token_id=str(self.params.nft_token_id),
            callable="get_balances",
            kwargs=ContractApiMessage.Kwargs(kwargs),
        )
        
        # Create and return the contract API dialogue
        contract_api_dialogue = contract_api_dialogues.create_with_message(request)

        # Send the API call to the outbox (non-blocking)
        self.context.outbox.put_message(message=contract_api_dialogue.last_incoming_message)

    async def async_act(self) -> None:
        """Perform the voting act asynchronously. Act only if this behaviour matches the current round."""
        if not isinstance(self.context.round_sequence.current_round, self.matching_round):
            return

        # Get the list of registered agents and initiate their balance check
        for agent in self.synchronized_data.registered_agents:
            await self._get_balance(self.context.ledger_apis.get_api(self.context.default_ledger_id), agent)

        # Instead of determining candidates in this behaviour, this will be done in the rounds.py 'end_block()' method.
        # So, we just mark this behavior as done after initiating balance checks.
        self.set_done()

        # Note that the follow-up after the balance check, like creating and sending the 'StartVotingPayload',
        # will now be handled in the corresponding round in 'rounds.py' based on the results from the balance checks.
        # This maintains the data synchronization and decision-making logic within the 'rounds.py' and adheres to the Autonolas framework guidelines.

class TransferFundsBehaviour(TickerBehaviour):
    """This behaviour executes the fund transfer action based on voting results."""

    def setup(self):
        """Setup the behaviour."""
        # Set up the Ethereum Api
        self.ledger_api = EthereumApi(**self.context.ledger_apis.apis.get("ethereum"))
        
        
        #Load contract and token id from AEA config
        self.contract_id = self.context.params.nft_contract_id
        self.token_id = self.context.params.nft_token_id

    def act(self) -> None:
        """Perform the NFT transfer action."""
        # Check if it's the appropriate round
        if self.is_matching_round_active(TransferFundsRound):
            hot_potato_holder = self.context.state.get('nft_holder')
            winning_agent = self.context.state.get('voting_winner')

            # Fetch the contract instance
            contract = self.ledger_api.get_contract_instance(contract_id=self.contract_id)
            transfer_function = contract.get_function_by_signature('transferFrom(address,address,uint256)')

            # Create the transaction to transfer the NFT
            tx = transfer_function.build_transaction({
                "from": hot_potato_holder,
                "to": winning_agent,
                "tokenId": self.token_id
            })

            # Sign and send the transaction
            tx_signed = self.context.ledger_apis.sign_transaction(self.ledger_api.identifier, tx, hot_potato_holder)
            tx_digest = self.context.ledger_apis.send_signed_transaction(self.ledger_api.identifier, tx_signed)

            # Handle transaction submission outcome
            if tx_digest is not None:
                self.context.logger.info(f"Transaction successfully sent with digest: {tx_digest}")
                # Set any flags or perform any follow-up needed after successful transfer
            else:
                self.context.logger.error("Transaction failed to submit.")

    def is_matching_round_active(self, round_class) -> bool:
        """Determine if the matching round is currently active."""
        # Placeholder for checking if the matching round is active based on the agent's state machine
        return isinstance(self.context.round_sequence.current_round, round_class)

    def tick_interval(self) -> float:
        """Specify the tick interval."""
        # Set the desired interval between calls to this behaviour's `act` method
        return 1.0  # Placeholder: set to desired interval in seconds


class WaitForNFTTransferBehaviour(TickerBehaviour):
    """This behaviour manages waiting for confirmation of NFT transfers."""

    def setup(self):
        """Setup the behaviour."""
        # Placeholder for setup, if needed.
        self.ledger_api = self.context.ledger_apis.get_api('ethereum')  # set as ethereum for now, need to look up naming convention for gnosis chain id

        # Fetch details from the `aea-config.yaml` file
        self.contract_id = self.context.params.nft_contract_id
        self.token_id = self.context.params.nft_token_id
        # self.expected_new_owner = self.context.params.expected_new_owner # This isn't relevant I don't think

    def act(self) -> None:
        """Perform async action to confirm NFT transfer."""
        # In this example, assume that self.ledger_api has been instantiated correctly
        # and that there is a method available to get the current owner of the token
        nft_contract = self.ledger_api.get_contract(self.contract_id)
        # Replace 'get_owner' with the actual method from your NFT contract ABI
        new_owner_query = nft_contract.functions.get_owner(self.token_id)

        # Using `self.ledger_api.api_call()` to make a non-blocking contract call
        new_owner = self.ledger_api.api_call(new_owner_query)

        if new_owner == self.expected_new_owner:
            self.context.logger.info(f"NFT (Token ID: {self.token_id}) ownership confirmed for {new_owner}.")
            
            
        else:
            self.context.logger.warning(f"NFT (Token ID: {self.token_id}) not yet confirmed for {new_owner}.")
            

    def tick_interval(self) -> float:
        """Specify the tick interval."""
        # Set the desired interval between 'act' method calls
        return 10.0  # Placeholder: set to desired interval in seconds


class ConsensusTendermintServiceRoundBehaviour(AbstractRoundBehaviour):
    """Manage the sequencing of round behaviours in the consensus service."""

    initial_behaviour_cls = WaitForNFTTransferBehaviour
    abci_app_cls = ConsensusTendermintServiceAbciApp
    behaviours: Set[Type[BaseBehaviour]] = {
        CheckResultsBehaviour,
        StartVotingBehaviour,
        TransferFundsBehaviour,
        WaitForNFTTransferBehaviour,
    }

    def act(self) -> None:
        """Switch to the appropriate behaviour based on the current round."""
        current_round = self.context.round_sequence.current_round
        if current_round:
            # Map the current round to the appropriate behaviour
            mapping = {
                StartVotingRound: StartVotingBehaviour,
                CheckResultsRound: CheckResultsBehaviour,
                TransferFundsRound: TransferFundsBehaviour,
                WaitForFundsRound: WaitForNFTTransferBehaviour,
            }
            current_behaviour = mapping.get(type(current_round), None)
            if current_behaviour:
                # Run the current behaviour
                self.context.behaviours.activate(current_behaviour)

class SynchronizedData(BaseSynchronizedData):
    """Handle the synchronized data across behaviours and rounds."""

    def __init__(self):
        """Initialize the synchronized data."""
        super().__init__()
        self._funds = {}
        self._votes = {}
        self.selected_receiver = None
        self.last_transaction_hash = None
        self.nft_holder = None
        self.nft_token_id = None

    @property
    def funds(self) -> Dict[str, float]:
        """Get the current funds for all agents."""
        return self._funds

    @property
    def votes(self) -> Dict[str, str]:
        """Get all current votes."""
        return self._votes
