import random

# the module file includes optional plugins called during the conversation. Each must be passed an event, as well as optional kwargs
# the module must return a tuple of (status, message) where status is either "end_interaction" or "continue_interaction"
# completed modules must be added to the module_registry dictionary at the bottom of the file
# they are called from the execute_optional_modules function in utils.py according to execution_time


def randomisation(split, control_group_message):
    """Randomly assign users to a control group, and send them a message"""

    random_number = random.random()

    # TODO store randomisation in a database

    if random_number < split:
        return "end_interaction", "control", control_group_message
    else:
        return "continue_interaction", "treatment"


module_registry = {
    "randomisation": randomisation,
}
