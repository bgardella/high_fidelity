import boto3
import time

"""
AWS SCRIPT TO RESTORE EBS SNAPSHOTS INTO EBS VOLUMES

author: Ben Gardella
date: 3/7/2016

"""

######### STATIC PARAMETERS #######################

vol_id_list = [ 'vol-577ef8ea',
                'vol-547ef8e9',
                'vol-567ef8eb']

ami = 'ami-d1f482b1' # Amazon Linux AMI 2015.09.2
instance_type = 't2.micro'
availability_zone = 'us-west-1c'
my_subnet_id = 'subnet-2d278f74'

device_name_map = { vol_id_list[0]: '/dev/sdf',
                    vol_id_list[1]: '/dev/sdg',
                    vol_id_list[2]: '/dev/sdh' }

report_email = 'bgardella@gmail.com'

####################################################

print "Restore Script Starting..."

# Client
ec2client = boto3.client('ec2')

# Resource
ec2resource = ec2 = boto3.resource('ec2')

# Find most recent snapshot of each volume

ss_response = ec2client.describe_snapshots(
        Filters=[{
            'Name': 'volume-id',
            'Values': vol_id_list
        }]
    )

# build map of most recent snapshots to restore...

ss_map = {}
for ss in ss_response['Snapshots']:
    if ss['Progress'] == '100%':
        if ss['VolumeId'] in ss_map:
            shot = ss_map[ss['VolumeId']]
            if ss['StartTime'] > shot['StartTime']:
                ss_map[ss['VolumeId']] = ss
        else:
            ss_map[ss['VolumeId']] = ss

print "The following volumes will be mounted to a new instance:"

for k,v in ss_map.items():
    print k+' : '+v['SnapshotId']+' : '+v['StartTime'].strftime("%Y-%m-%d_%H:%M:%S.%f")

# Build Block Device Data Block
block_device_arr = []

for k,v in ss_map.items():
    block_device_data = {}
    block_device_data['DeviceName'] = device_name_map[k]
    ebs = {}
    ebs['SnapshotId'] = v['SnapshotId']
    ebs['VolumeSize'] = 1
    ebs['DeleteOnTermination'] = True
    ebs['VolumeType'] = 'gp2'
    block_device_data['Ebs'] = ebs
    block_device_arr.append(block_device_data)

user_data_cmd_arr = []
user_data_cmd_arr.append('#!/bin/bash\n')
user_data_cmd_arr.append('yum install sendmail\n')
user_data_cmd_arr.append('mkdir /vol_1\n')
user_data_cmd_arr.append('mkdir /vol_2\n')
user_data_cmd_arr.append('mkdir /vol_3\n')
user_data_cmd_arr.append('mount /dev/xvdf /vol_1\n')
user_data_cmd_arr.append('mount /dev/xvdg /vol_2\n')
user_data_cmd_arr.append('mount /dev/xvdh /vol_3\n')

user_data_cmd_arr.append('if test -f "/vol_1/restore.successful"; then echo "Subject: Vol_1 Restore Successful" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';else echo "Subject: Vol_1 Restore FAILED" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';fi\n')

user_data_cmd_arr.append('if test -f "/vol_2/restore.successful"; then echo "Subject: Vol_2 Restore Successful" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';else echo "Subject: Vol_2 Restore FAILED" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';fi\n')

user_data_cmd_arr.append('if test -f "/vol_3/restore.successful"; then echo "Subject: Vol_3 Restore Successful" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';else echo "Subject: Vol_3 Restore FAILED" | sendmail -v ')
user_data_cmd_arr.append(report_email)
user_data_cmd_arr.append(';fi\n')

user_data = ''.join(user_data_cmd_arr)

# create new micro instance
inst_response = ec2resource.create_instances(
        ImageId=ami,
        KeyName='boomboom',
        MinCount=1,
        MaxCount=1,
        UserData=user_data,
        InstanceType=instance_type,
        Monitoring={
            'Enabled': False
        },
        Placement={
            'AvailabilityZone': availability_zone
        },
        BlockDeviceMappings=block_device_arr,
        NetworkInterfaces=[{
            'DeviceIndex': 0,
            'AssociatePublicIpAddress': True,
            'SubnetId': my_subnet_id
            }]
    )

inst_obj = inst_response[0]
inst_id = inst_obj.instance_id

# wait until the instance is up and running
print "Waiting for Instance ["+inst_id+"] to initialize..."
inst_obj.wait_until_running()

# now check the status
print "Checking status of instance..."
waiter = ec2client.get_waiter('instance_status_ok')
waiter.wait(
        InstanceIds=[ inst_id ],
        Filters=[{
                'Name': 'instance-status.reachability',
                'Values': [ 'passed' ]
            }]
    )

# give the instance a bit of time to go thru the UserData commands...
print "Wait a bit more for safety..."
time.sleep(15)

# shut the instance down (should clean up volumes as well)
print "Terminating Instance ["+inst_id+"]..."
inst_obj.terminate()

inst_obj.wait_until_terminated()

print "Instance ["+inst_id+"] Terminated!"