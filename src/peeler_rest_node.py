"""REST-based node for Brooks Xpeel device"""

import time

from madsci.client.resource_client import ResourceClient
from madsci.common.types.action_types import ActionFailed, ActionSucceeded
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.auth_types import OwnershipInfo
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types.definitions import (
    ContinuousConsumableResourceDefinition,
    SlotResourceDefinition,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from peeler_interface import Peeler


class PeelerNodeConfig(RestNodeConfig):
    """Configuration for the Peeler node."""

    device_port: str


class PeelerNode(RestNode):
    """A node to control the Brooks Xpeel peeler device."""

    peeler_interface: Peeler = None
    config_model = PeelerNodeConfig

    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""
        try:
            if self.config.resource_server_url:
                self.resource_client = ResourceClient(url=self.config.resource_server_url)
                self.resource_owner = OwnershipInfo(node_id=self.node_definition.node_id)
                self.peeler_deck_resource = self.resource_client.init_resource(
                    SlotResourceDefinition(
                        resource_name="peeler_deck",
                        owner=self.resource_owner,
                    )
                )
                self.peel_resource = self.resource_client.init_resource(
                    ContinuousConsumableResourceDefinition(
                        resource_name="peel",
                        owner=self.resource_owner,
                    )
                )
            else:
                self.resource_client = None
                self.peeler_deck_resource = None
                self.peel_resource = None

            self.logger.info("Node initializing...")
            self.peeler_interface = Peeler(
                host_path=self.config.device_port,
                resource_client=self.resource_client,
                peeler_deck_resource=self.peeler_deck_resource,
                peel_resource=self.peel_resource,
            )
        except Exception as err:
            self.logger.log_error(f"Error starting the Peeler Node: {err}")
            self.startup_has_run = False
        else:
            self.startup_has_run = True
            self.logger.log("Peeler node initialized!")

    def shutdown_handler(self) -> None:
        """Called to close connections to devices or clean up any other resources."""
        try:
            self.logger.log("Shutting down Peeler node...")
            if self.peeler_interface:
                self.peeler_interface.disconnect()
                self.logger.log("Peeler node closed!")
                self.shutdown_has_run = True
                del self.peeler_interface
                self.peeler_interface = None
            else:
                self.logger.log("Peeler node not initialized, nothing to close.")
        except Exception as err:
            self.logger.log_error(f"Error shutting down the Peeler Node: {err}")

    def state_handler(self):
        """Periodically checks the state of the Peeler device and updates the node's state."""
        if self.peeler_interface:
            self.peeler_interface.get_status()
        else:
            self.logger.log_error("Peeler interface is not initialized")
            return

        if self.peeler_interface.status_msg == 3:
            self.node_state = {
                "peeler_status_code": "ERROR",
            }
            self.logger.log_error("peeler error")
        elif self.peeler_interface.status_msg == 0:
            self.node_state = {
                "peeler_status_code": "READY",
            }
        else:
            self.node_state = {
                "peeler_status_code": "UNKNOWN",
            }
            self.logger.log_error("peeler status unknown")

    @action(name="peel", description="Peel a plate peel")
    def peel(self):
        """Peel a plate"""
        try:
            self.peeler_interface.seal_check()
            self.peeler_interface.peel(1, 2.5)
            time.sleep(15)
        except Exception as err:
            self.logger.log_error(f"Error during peeling: {err}")
            return ActionFailed(errors=f"Peeling failed: {err}")
        else:
            return ActionSucceeded()

    def reset_peel_resource(self) -> AdminCommandResponse:
        """Reset the peel resource"""
        try:
            if self.resource_client and self.peeler_deck_resource and self.peel_resource:
                self.resource_client.empty(self.peel_resource)
            else:
                return AdminCommandResponse(
                    success=False, data={"error": "Resource client or resources not initialized"}
                )
            return AdminCommandResponse(data={"Peel resource empty"})
        except Exception:
            return AdminCommandResponse(success=False)


if __name__ == "__main__":
    peeler_node = PeelerNode()
    peeler_node.start_node()
