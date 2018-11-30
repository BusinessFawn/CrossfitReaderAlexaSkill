# -*- coding: utf-8 -*-
import logging
import six
import dynamo_unwrapper

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler, \
    AbstractRequestInterceptor, AbstractResponseInterceptor
from ask_sdk_model.dialog import ElicitSlotDirective, DelegateDirective
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model.ui import SimpleCard
from ask_sdk_model import Response, DialogState, SlotConfirmationStatus
from ask_sdk_model.slu.entityresolution import StatusCode

SKILL_NAME = "Crossfit Workout Reader"
HELP_MESSAGE = "You can ask to list workouts, to select a specific one, or, you can say exit... " \
               "What can I help you with?"
HELP_REPROMPT = "What can I help you with?"
STOP_MESSAGE = "Goodbye!"
FALLBACK_MESSAGE = "Doesn't seem like I can help with that.."
FALLBACK_REPROMPT = 'What can I help you with?'
EXCEPTION_MESSAGE = "Sorry. I cannot help you with that."
list_required_slots = ['WorkoutType', 'Duration']

sb = SkillBuilder()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Request Handler classes
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for skill launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In LaunchRequestHandler")
        speech = 'Welcome to the crossfit workout holder, I can list workouts or tell you random options'
        reprompt = "I can list workouts or tell you random options"
        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response


# Built-in Intent Handlers
class InProgressGetWorkoutHandler(AbstractRequestHandler):
    """Handler for Skill Launch and ListWorkouts Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("GetWorkout")(handler_input) and \
               handler_input.request_envelope.request.dialog_state != DialogState.COMPLETED

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In InProgressGetWorkoutHandler")
        current_intent = handler_input.request_envelope.request.intent
        return handler_input.response_builder.add_directive(
            DelegateDirective(
                updated_intent=current_intent
            )).response


class CompletedGetWorkoutHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("GetWorkout")(handler_input)
                and handler_input.request_envelope.request.dialog_state == DialogState.COMPLETED)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CompletedGetWorkoutHandler")
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        speech = dynamo_unwrapper.get_workout_item(slot_values['WorkoutId']['resolved'])

        return handler_input.response_builder.speak(speech).response


# Built-in Intent Handlers
class InProgressListWorkoutsHandler(AbstractRequestHandler):
    """Handler for Skill Launch and ListWorkouts Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("ListWorkouts")(handler_input) and \
               handler_input.request_envelope.request.dialog_state != DialogState.COMPLETED

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In InProgressListWorkoutsHandler")
        current_intent = handler_input.request_envelope.request.intent
        for slot_name, current_slot in six.iteritems(
                current_intent.slots):
            if slot_name not in ["article", "at_the", "I_Want"]:
                if (current_slot.confirmation_status != SlotConfirmationStatus.CONFIRMED
                        and current_slot.resolutions
                        and current_slot.resolutions.resolutions_per_authority[0]):
                    if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                        if len(current_slot.resolutions.resolutions_per_authority[0].values) > 1:
                            prompt = "Which would you like "

                            values = " or ".join([e.value.name for e in current_slot.resolutions.resolutions_per_authority[0].values])
                            prompt += values + " ?"
                            return handler_input.response_builder.speak(
                                prompt).ask(prompt).add_directive(
                                ElicitSlotDirective(slot_to_elicit=current_slot.name)
                            ).response
                    elif current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_NO_MATCH:
                        if current_slot.name in list_required_slots:
                            prompt = "What {} are you looking for?".format(current_slot.name)

                            return handler_input.response_builder.speak(
                                prompt).ask(prompt).add_directive(
                                ElicitSlotDirective(
                                    slot_to_elicit=current_slot.name
                                )).response

        return handler_input.response_builder.add_directive(
            DelegateDirective(
                updated_intent=current_intent
            )).response


class CompletedListWorkoutsHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("ListWorkouts")(handler_input)
                and handler_input.request_envelope.request.dialog_state == DialogState.COMPLETED)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CompletedListWorkoutsHandler")
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        logger.info("slot vals: {}".format(slot_values))
        speech = dynamo_unwrapper.query_workout_items(slot_values['Duration']['resolved'],
                                                      slot_values['WorkoutType']['resolved'])

        return handler_input.response_builder.speak(speech).response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In HelpIntentHandler")

        handler_input.response_builder.speak(HELP_MESSAGE).ask(
            HELP_REPROMPT).set_card(SimpleCard(
            SKILL_NAME, HELP_MESSAGE))
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CancelOrStopIntentHandler")

        handler_input.response_builder.speak(STOP_MESSAGE)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """Handler for Fallback Intent.
    AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")

        handler_input.response_builder.speak(FALLBACK_MESSAGE).ask(
            FALLBACK_REPROMPT)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In SessionEndedRequestHandler")

        logger.info("Session ended reason: {}".format(
            handler_input.request_envelope.request.reason))
        return handler_input.response_builder.response


# Exception Handler
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch all exception handler, log exception and
    respond with custom message.
    """

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.info("In CatchAllExceptionHandler")
        logger.error(exception, exc_info=True)

        handler_input.response_builder.speak(EXCEPTION_MESSAGE).ask(
            HELP_REPROMPT)

        return handler_input.response_builder.response


# Request and Response loggers
class RequestLogger(AbstractRequestInterceptor):
    """Log the alexa requests."""

    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logger.debug("Alexa Request: {}".format(
            handler_input.request_envelope.request))


class ResponseLogger(AbstractResponseInterceptor):
    """Log the alexa responses."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.debug("Alexa Response: {}".format(response))


def get_slot_values(filled_slots):
    """Return slot values with additional info."""
    slot_values = {}
    logger.info("Filled slots: {}".format(filled_slots))

    for key, slot_item in six.iteritems(filled_slots):
        name = slot_item.name
        try:
            status_code = slot_item.resolutions.resolutions_per_authority[0].status.code

            if status_code == StatusCode.ER_SUCCESS_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.resolutions.resolutions_per_authority[0].values[0].value.name,
                    "is_validated": True,
                }
            elif status_code == StatusCode.ER_SUCCESS_NO_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.value,
                    "is_validated": False,
                }
            else:
                pass
        except (AttributeError, ValueError, KeyError, IndexError, TypeError) as e:
            logger.info("Couldn't resolve status_code for slot item: {}".format(slot_item))
            logger.info(e)
            slot_values[name] = {
                "synonym": slot_item.value,
                "resolved": slot_item.value,
                "is_validated": False,
            }
    logger.info("slot_values: {}".format(slot_values))
    return slot_values


# Register intent handlers
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(InProgressGetWorkoutHandler())
sb.add_request_handler(CompletedGetWorkoutHandler())
sb.add_request_handler(InProgressListWorkoutsHandler())
sb.add_request_handler(CompletedListWorkoutsHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Register exception handlers
sb.add_exception_handler(CatchAllExceptionHandler())

sb.add_global_request_interceptor(RequestLogger())
sb.add_global_response_interceptor(ResponseLogger())

# Handler name that is used on AWS lambda
lambda_handler = sb.lambda_handler()
