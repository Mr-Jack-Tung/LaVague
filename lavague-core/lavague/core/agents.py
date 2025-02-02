import logging
import os
import shutil
from typing import Dict
from lavague.core.action_engine import ActionEngine
from lavague.core.python_engine import PythonEngine
from lavague.core.world_model import WorldModel
from lavague.core.navigation import NavigationControl
from lavague.core.utilities.format_utils import (
    extract_next_engine,
    extract_world_model_instruction,
)
from lavague.core.logger import AgentLogger
from lavague.core.memory import ShortTermMemory
from lavague.core.base_driver import BaseDriver

from lavague.core.utilities.telemetry import send_telemetry

logging_print = logging.getLogger(__name__)
logging_print.setLevel(logging.INFO)
format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(format)
logging_print.addHandler(ch)
logging_print.propagate = False


class WebAgent:
    """
    Web agent class, for now only works with selenium.
    """

    def __init__(
        self,
        world_model: WorldModel,
        action_engine: ActionEngine,
        n_steps: int = 10,
        clean_screenshot_folder: bool = True,
    ):
        self.driver: BaseDriver = action_engine.driver
        self.action_engine: ActionEngine = action_engine
        self.world_model: WorldModel = world_model
        self.st_memory = ShortTermMemory()

        self.n_steps = n_steps

        self.clean_screenshot_folder = clean_screenshot_folder

        self.logger: AgentLogger = AgentLogger()

        self.action_engine.set_logger_all(self.logger)
        self.world_model.set_logger(self.logger)
        self.st_memory.set_logger(self.logger)

    def get(self, url):
        self.driver.goto(url)

    def run(self, objective: str, user_data=None, display: bool = False):
        driver: BaseDriver = self.driver
        logger = self.logger
        n_steps = self.n_steps
        self.action_engine.set_display(display)

        st_memory = self.st_memory
        world_model = self.world_model

        if self.clean_screenshot_folder:
            try:
                if os.path.isdir("screenshots"):
                    shutil.rmtree("screenshots")
                logging_print.info("Screenshot folder cleared")
            except:
                pass

        obs = driver.get_obs()

        logger.new_run()
        for _ in range(n_steps):
            current_state, past = st_memory.get_state()

            world_model_output = world_model.get_instruction(
                objective, current_state, past, obs
            )
            logging_print.info(world_model_output)
            next_engine_name = extract_next_engine(world_model_output)
            instruction = extract_world_model_instruction(world_model_output)

            if next_engine_name == "COMPLETE" or next_engine_name == "SUCCESS":
                output = instruction
                logging_print.info("Objective reached. Stopping...")

                logger.add_log(obs)
                logger.end_step()
                break

            success, output = self.action_engine.dispatch_instruction(
                next_engine_name, instruction
            )
            st_memory.update_state(instruction, next_engine_name, success, output)

            logger.add_log(obs)
            logger.end_step()

            obs = driver.get_obs()
        send_telemetry(logger.return_pandas())
        return output
