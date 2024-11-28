import boto3
import json
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timedelta

# EC2 클라이언트 생성 (ap-northeast-1 리전 지정)
ec2 = boto3.client('ec2', region_name='ap-northeast-1')

def get_slots(intent_request):
    return intent_request['sessionState']['intent']['slots']
    
def get_slot(intent_request, slotName):
    slots = get_slots(intent_request)
    if slots is not None and slotName in slots and slots[slotName] is not None:
        return slots[slotName]['value']['interpretedValue']
    else:
        return None 

def get_session_attributes(intent_request):
    sessionState = intent_request['sessionState']
    if 'sessionAttributes' in sessionState:
        return sessionState['sessionAttributes']

    return {}

def elicit_intent(intent_request, session_attributes, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitIntent'
            },
            'sessionAttributes': session_attributes
        },
        'messages': [ message ] if message != None else None,
        'requestAttributes': intent_request['requestAttributes'] if 'requestAttributes' in intent_request else None
    }


def close(intent_request, session_attributes, fulfillment_state, message):
    intent_request['sessionState']['intent']['state'] = fulfillment_state
    return {
        'sessionState': {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'Close'
            },
            'intent': intent_request['sessionState']['intent']
        },
        'messages': [message],
        'sessionId': intent_request['sessionId'],
        'requestAttributes': intent_request['requestAttributes'] if 'requestAttributes' in intent_request else None
    }


def instanceList(intent_request):
    session_attributes = get_session_attributes(intent_request)

    # 인스턴스 정보를 저장할 리스트
    instances = []
    
    # ap-northeast-1 리전의 인스턴스 정보 수집
    response = ec2.describe_instances()
    
    instance_info = []
    
    index = 0

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            
            index = index + 1
           # 인스턴스 정보 문자열 생성

            if 'Tags' in instance:
                for tag in instance['Tags']:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break

            info = f"{index}번째 인스턴스 {instance_name}, " \
                   f" 타입은 {instance['InstanceType']}, " \
                   f" 현재 {instance['State']['Name']} 상태입니다. " 
                   #f" IP는 {instance.get('PublicIpAddress', 'N/A')}  입니다. " 

            instance_info.append(info)

    message =  {
            'contentType': 'PlainText',
            'content': "".join(instance_info)
        }


    fulfillment_state = "Fulfilled"    
    return close(intent_request, session_attributes, fulfillment_state, message)   

def instanceAction(intent_request):
    session_attributes = get_session_attributes(intent_request)
    slots = get_slots(intent_request)
    instanceNumber = get_slot(intent_request, 'InstanceNumber')
    instanceAction = get_slot(intent_request, 'Action')

    # 인스턴스 정보를 저장할 리스트
    instances = []
    
    # ap-northeast-1 리전의 인스턴스 정보 수집
    response = ec2.describe_instances()
    
    instance_info = []
    
    index = 0
    found = False

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            try :
                index = index + 1
                if (index == int(instanceNumber)):
                    found = True

                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'Name':
                                instance_name = tag['Value']
                                break

                    if (instanceAction == "START"):
                        ec2.start_instances(InstanceIds=[instance['InstanceId']])
                        message = f"{index}번째 인스턴스 {instance_name}가 시작됐습니다."
                    elif (instanceAction == "STOP"):
                        ec2.stop_instances(InstanceIds=[instance['InstanceId']])
                        message = f"{index}번째 인스턴스 {instance_name}가 중단됐습니다."

            except Exception as e:
                message = f'작업 도중 문제가 발생했습니다. : {str(e)}'
    if (found == False):
        message = f'{instanceNumber}번째 인스턴스를 찾지 못했습니다. 목록을 확인해주세요.'

    message =  {
            'contentType': 'PlainText',
            'content': message
        }

    fulfillment_state = "Fulfilled"    
    return close(intent_request, session_attributes, fulfillment_state, message)   


def instanceCheck(intent_request):
    session_attributes = get_session_attributes(intent_request)
    
    # 인스턴스 정보를 저장할 리스트
    instances = []
    
    # ap-northeast-1 리전의 인스턴스 정보 수집
    response = ec2.describe_instances()
    
    instance_info = []
    
    index = 0

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            
            index = index + 1
           # 인스턴스 정보 문자열 생성

            instance_id = instance['InstanceId']

            cloudwatch = boto3.client('cloudwatch', region_name='ap-northeast-1')
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)

           # CloudWatch에서 CPU 사용률 데이터 가져오기
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )

            if 'Tags' in instance:
                for tag in instance['Tags']:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break

            cpu_util = 0
            if response['Datapoints']:
                cpu_util = response['Datapoints'][0]['Average']
            
            if cpu_util > 0.5:        
                info = f"인스턴스 {instance_name}, 아이디는 {instance_id}, " \
                        f" CPU 사용량은 {cpu_util:.2f}% 입니다. " \
                    #f" IP는 {instance.get('PublicIpAddress', 'N/A')}  입니다. " 

                instance_info.append(info)

    
    if(len(instance_info) > 0):
        messageContent = "".join(instance_info)
    else:
        messageContent = "해당하는 인스턴스가 없습니다."
    
    message =  {
            'contentType': 'PlainText',
            'content': messageContent
        }

    fulfillment_state = "Fulfilled"    
    return close(intent_request, session_attributes, fulfillment_state, message)   

def memberList(intent_request):
    session_attributes = get_session_attributes(intent_request)

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('SGHelperMembers')

    member_info = []
    
    response = table.scan()
    
    # 결과 처리 및 프린트
    items = response['Items']
    
    for item in items:
        for key, value in item.items():
                info = f"{value} "
            
                member_info.append(info)
    
    message =  {
            'contentType': 'PlainText',
            'content': "".join(member_info)
        }

    fulfillment_state = "Fulfilled"    
    return close(intent_request, session_attributes, fulfillment_state, message)   

def memberAdd(intent_request):
    session_attributes = get_session_attributes(intent_request)
    slots = get_slots(intent_request)
    memberName = get_slot(intent_request, 'MemberName')
    memberEmail = get_slot(intent_request, 'MemberEmail')

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('SGHelperMembers')

    item = {'memberID' : memberName, 'mail' : memberEmail}

    table.put_item(
        Item=item
    )

    message =  {
            'contentType': 'PlainText',
            'content': "팀원이 추가됐습니다"
        }

    fulfillment_state = "Fulfilled"    
    return close(intent_request, session_attributes, fulfillment_state, message)   

def dispatch(intent_request):
    intent_name = intent_request['sessionState']['intent']['name']
    response = None
    # Dispatch to your bot's intent handlers
    if intent_name == 'instanceList':
        return instanceList(intent_request)
    elif intent_name == 'instanceAction':
        return instanceAction(intent_request)
    elif intent_name == 'MemberList':
        return memberList(intent_request)
    elif intent_name == 'MemberAction':
        return memberAdd(intent_request)
    elif intent_name == 'InstanceCheck':
        return instanceCheck(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')

def lambda_handler(event, context):
    response = dispatch(event)
    return response