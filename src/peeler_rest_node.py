"""REST-based node for Brooks Xpeel device"""

from madsci.common.types.action_types import ActionResult, ActionSucceeded
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types.definitions import (
    DiscreteConsumableResourceDefinition,
    SlotResourceDefinition,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from peeler_interface import Peeler


class PeelerNodeConfig(RestNodeConfig):
    """Configuration for the Peeler node."""

    device_port: str
    """Which serial port to use for the peeler device."""
    check_for_plate: bool = False
    """Whether to check for a plate before peeling."""


class PeelerNode(RestNode):
    """A node to control the Brooks Xpeel peeler device."""

    peeler: Peeler = None
    config_model = PeelerNodeConfig
    config: PeelerNodeConfig = PeelerNodeConfig()
    module_version = "1.1.0"

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""
        if self.resource_client:
            self.plate_carrier = self.resource_client.init_resource(
                SlotResourceDefinition(
                    resource_name=f"{self.node_definition.node_name}_plate_nest",
                )
            )
            self.tape_supply = self.resource_client.init_resource(
                DiscreteConsumableResourceDefinition(
                    resource_name=f"{self.node_definition.node_name}_tape_supply",
                )
            )
            self.tape_takeup = self.resource_client.init_resource(
                DiscreteConsumableResourceDefinition(
                    resource_name=f"{self.node_definition.node_name}_tape_takeup",
                )
            )
        else:
            self.plate_carrier = None
            self.tape_supply = None
            self.tape_takeup = None

        self.peeler = Peeler(
            device_path=self.config.device_port,
            resource_client=self.resource_client,
            plate_carrier=self.plate_carrier,
            tape_supply=self.tape_supply,
            tape_takeup=self.tape_takeup,
            logger=self.logger,
        )
        self.peeler.connect()
        self.peeler.plate_check(self.config.check_for_plate)
        try:
            self.peeler.tape_remaining()
        except Exception:
            self.logger.log_error("Error getting tape remaining")

    def shutdown_handler(self) -> None:
        """Called to close connections to devices or clean up any other resources."""
        try:
            if self.peeler:
                del self.peeler
                self.peeler = None
        except Exception as err:
            self.logger.log_error(f"Error shutting down the Peeler Node: {err}")

    def state_handler(self) -> None:
        """Periodically checks the state of the Peeler device and updates the node's state."""
        if self.peeler:
            self.peeler.get_status()
        else:
            self.logger.log_error("Peeler interface is not initialized")
            return

        self.node_state["status_message"] = self.peeler.ready_message.model_dump(
            mode="json"
        )
        if self.peeler.tape_supply:
            self.node_state["tape_supply"] = self.peeler.tape_supply.quantity
        if self.peeler.tape_takeup:
            self.node_state["tape_takeup"] = self.peeler.tape_takeup.quantity

    @action(name="peel")
    def peel(self, param_set_num: int = 1, param_time: float = 2.5) -> ActionResult:
        """
        Peel a plate seal.

        :param param_set_num: The parameter set number to use for peeling.

            1: ["default -2 mm", "fast"]
            2: ["default -2 mm", "slow"]
            3: ["default", "fast"]
            4: ["default", "slow"]
            5: ["default +2 mm", "fast"]
            6: ["default +2 mm", "slow"]
            7: ["default +4 mm", "fast"]
            8: ["default +4 mm", "slow"]
            9: ["custom", "custom"]

        :param param_time: The time in seconds to wait for the peel to complete.
        """
        self.peeler.peel(param_set_num=param_set_num, param_time=param_time)
        return ActionSucceeded()

    @action(name="reset_peeler")
    def reset_peeler(self) -> ActionResult:
        """Returns elevator and conveyor to home location and gets fresh tape in place to use."""
        self.peeler.reset()

    def reset(self) -> AdminCommandResponse:
        """Returns elevator and conveyor to home location and gets fresh tape in place to use."""
        self.peeler.restart()
        return super().reset()


if __name__ == "__main__":
    peeler_node = PeelerNode()
    peeler_node.start_node()
