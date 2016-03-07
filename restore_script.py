import boto3
import pprint

"""
AWS SCRIPT TO RESTORE EBS SNAPSHOTS INTO EBS VOLUMES

author: Ben Gardella
date: 3/7/2016

"""

pp = pprint.PrettyPrinter(indent=4)

######### STATIC PARAMETERS #######################

vol_id_list = [ 'vol-2a204e7e',
                'vol-2b204e7f',
                'vol-3a204e6e']

ami = 'ami-d1f482b1' # Amazon Linux AMI 2015.09.2

availability_zone = 'us-west-1c'

device_name_map = { vol_id_list[0]: '/dev/sdf',
                    vol_id_list[1]: '/dev/sdg',
                    vol_id_list[2]: '/dev/sdh' }

####################################################


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

for k,v in ss_map.items():
    print k+' : '+v['SnapshotId']+' : '+v['StartTime'].strftime("%Y-%m-%d_%H:%M:%S.%f")

# Restore volumes from Snapshots
'''
new_vols = []
for k,v in ss_map.items():

    json_resp = ec2client.create_volume(
        DryRun=False,
        Size=1,
        SnapshotId=v['SnapshotId'],
        AvailabilityZone=availability_zone,
        VolumeType='gp2'
        )

    new_vol_id = json_resp['VolumeId']
    print "New Volume: %s" % new_vol_id
    new_vols.append(new_vol_id)

    tag = ec2client.create_tags(
        DryRun=False,
        Resources=[new_vol_id],
        Tags=[{'Key': 'Name', 'Value': 'from-'+v['SnapshotId']}]
        )
    if tag['ResponseMetadata']['HTTPStatusCode'] == 200:
        print "New Volume: %s is tagged!" % new_vol_id
    else:
        print "New Volume: %s tagging failed!" % new_vol_id
'''

block_device_arr = []

for k,v in ss_map.items():
    block_device_data = {}
#    block_device_data['VirtualName'] = k
    block_device_data['DeviceName'] = device_name_map[k]
    ebs = {}
    ebs['SnapshotId'] = v['SnapshotId']
    ebs['VolumeSize'] = 1
    ebs['DeleteOnTermination'] = True
    ebs['VolumeType'] = 'gp2'
    block_device_data['Ebs'] = ebs
    block_device_arr.append(block_device_data)


# create new micro instance
inst_response = ec2resource.create_instances(
        ImageId=ami,
        MinCount=1,
        MaxCount=1,
        UserData='cd /usr/local; ls -la',
        InstanceType='t2.micro',
        Monitoring={
            'Enabled': False
        },
        SubnetId='subnet-2d278f74',
        Placement={
            'AvailabilityZone': availability_zone
        },
        BlockDeviceMappings=block_device_arr
    )

pp.pprint(inst_response)

# attach new volumes