import boto3
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def workout_structure(structure: list, workout_type: str):
    speech = ''

    for l in range(len(structure)):
        speech = speech + 'Item {}\n'.format(l + 1)
        if workout_type == 'AMRAP':
            speech = speech + 'as many rounds as possible in {} minutes '.format(structure[l]['MoveDuration'][2:-1])
        elif workout_type == 'REPS':
            speech = speech + "as quickly as possible with a {} minute cap ".format(structure[l]['MoveDuration'][2:-1])
        else:
            speech = speech + 'for {} iterations of {} minutes '.format(structure[l]['Cycle'],
                                                                        structure[l]['MoveDuration'][2:-1])
        for i in structure[l]['MoveList']:
            speech = speech + '{} {} times. '.format(i['Move'], i['Reps'])

    return speech


def traverse_list(wrapped_list: list):
    unwrapped_list = []
    for l in wrapped_list:
        unwrapped_list.append(item_unwrapper(l))
    return unwrapped_list


def traverse_dict(wrapped_dict: dict):
    unwrapped_dict = {}
    for k, v in wrapped_dict.items():
        unwrapped_dict[k] = item_unwrapper(v)
    return unwrapped_dict


def item_unwrapper(dynamo_dict: dict):
    unwrapped_dynamo_dict = {}
    for key, val in dynamo_dict.items():
        if key == 'L':
            return list(val)
        elif key == 'S':
            return str(val)
        elif key == 'N':
            return int(val)
        elif val.get('N'):
            unwrapped_dynamo_dict[key] = int(val['N'])
        elif val.get('S'):
            unwrapped_dynamo_dict[key] = str(val['S'])
        elif val.get('L'):
            unwrapped_dynamo_dict[key] = traverse_list(val['L'])
        elif val.get('M'):
            unwrapped_dynamo_dict[key] = traverse_dict(val['M'])
        elif key == 'M':
            return dict(item_unwrapper(val))
    return unwrapped_dynamo_dict


def get_workout_item(workout_id: int) -> str:
    dynamodb_client = boto3.client('dynamodb')

    dynamodb_dict = dynamodb_client.get_item(TableName='CrossfitWorkouts', Key={'WorkoutId': {'N': str(workout_id)}})
    if not dynamodb_dict:
        return "I'm sorry, it doesn't seem that I have that workout. Please try listing the available workouts using " \
               "List Workouts"
    logger.info('dynamodb_dict: {}'.format(dynamodb_dict))
    unwrapped_dict = item_unwrapper(dynamodb_dict['Item'])
    logger.info('unwrapped_dict: {}'.format(unwrapped_dict))

    speech = 'Your workout will be {} minutes. Welcome to {}. '.format(unwrapped_dict['WorkoutDuration'][2:-1],
                                                                       unwrapped_dict['WorkoutName'])

    speech = speech + workout_structure(unwrapped_dict['Structure'], unwrapped_dict['WorkoutType'])

    return speech


def query_workout_items(workout_duration: str, workout_type: str):

    dynamodb_client = boto3.client('dynamodb')

    logger.info("TableName='CrossfitWorkouts', IndexName='WorkoutType-WorkoutDuration-index',"
                "KeyConditionExpression='WorkoutType = :workout_type ' "
                "'AND WorkoutDuration <= :workout_duration', "
                "ExpressionAttributeValues="
                ':workout_type": "S": {}, ":workout_duration": "S": {}'.format(workout_type, workout_duration))

    item_list = dynamodb_client.query(TableName='CrossfitWorkouts', IndexName='WorkoutType-WorkoutDuration-index',
                                      KeyConditionExpression='WorkoutType = :workout_type '
                                                             'AND WorkoutDuration <= :workout_duration',
                                      ExpressionAttributeValues={
                                        ":workout_type": {"S": workout_type},
                                        ":workout_duration": {"S": workout_duration}
                                      })

    logger.info('wrapped items: {}'.format(item_list["Items"]))
    unwrapped_list = []
    for item in item_list['Items']:
        unwrapped_list.append(item_unwrapper(item))

    if len(unwrapped_list) > 1:
        speech = "I found {} workouts. ".format(len(unwrapped_list))
    elif len(unwrapped_list) == 1:
        speech = "I found a workout for you. "
    else:
        return "I wasn't able to find any workouts for those parameters. Try some different options."

    logger.info('unwrapped list: {}'.format(unwrapped_list))
    for single_workout_item in unwrapped_list:
        speech = speech + 'ID {}, {}. '.format(single_workout_item['WorkoutId'], single_workout_item['WorkoutName'])
    return speech


if __name__ == '__main__':
    input_dict = {
        "Duration": {
            "S": "PT20M"
        },
        "Id": {
            "N": "1"
        },
        "Name": {
            "S": "Squat Out of Here"
        },
        "Structure": {
            "L": [
                {
                    "M": {
                        "Cycle": {
                            "N": "5"
                        },
                        "MoveDuration": {
                            "S": "PT4M"
                        },
                        "MoveList": {
                            "L": [
                                {
                                    "M": {
                                        "Move": {
                                            "S": "Back Squat"
                                        },
                                        "Reps": {
                                            "N": "13"
                                        }
                                    }
                                },
                                {
                                    "M": {
                                        "Move": {
                                            "S": "Front Squat"
                                        },
                                        "Reps": {
                                            "N": "7"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            ]
        },
        "WorkoutType": {
            "S": "EMOM"
        }
    }

    output_dict = item_unwrapper(input_dict)
    print('output_dict: {}'.format(output_dict))

    workout = workout_structure(output_dict['Structure'])

    print('finished: {}'.format(workout))