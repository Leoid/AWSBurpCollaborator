#::--Author B1twis3 ::--
import boto3
import sys
import os
import botocore
import paramiko
from datetime import datetime

domain_name = str(sys.argv[1])

r53 = boto3.client('route53')
ec2 = boto3.resource('ec2')

# Creating VPC
print("[*] Creating a VPC")
vpc = ec2.create_vpc(CidrBlock='172.31.0.0/16')
vpc.create_tags(Tags=[{"Key":"Name","Value":"Default_vpc"}])
vpc.wait_until_available()
print("[+] VPC ID: "+vpc.id)

# Creating IG
print("[*] Creating Internet Gateway")
ig = ec2.create_internet_gateway()
vpc.attach_internet_gateway(InternetGatewayId=ig.id)
print("[+] Internet Gateway ID: "+ig.id)

# Creating Routing Table
print("[*] Creating Routing Table")
route_table = vpc.create_route_table()
route = route_table.create_route(DestinationCidrBlock='0.0.0.0/0',GatewayId=ig.id)
print("[+] Routing Table ID: "+route_table.id)

# Creating Subnet
print("[*] Creating Subnet")
subnet = ec2.create_subnet(CidrBlock='172.31.17.0/24',VpcId=vpc.id)
print("[+] Subnet ID: "+subnet.id)

# Configuring the Route Table to the Subnet
print("[+] Associating the Route Table with the Subnet")
route_table.associate_with_subnet(SubnetId=subnet.id)


# Creating Security Group [All TCP or you can only confiure the required ports]
print("[*] Creating Security Group")
security_group = ec2.create_security_group(
        GroupName='BurpCollabGroup',Description='BurpSuite Private Collaborator',VpcId=vpc.id)
security_group.authorize_ingress(
       CidrIp='0.0.0.0/0',
       IpProtocol='tcp',
       FromPort=0,
       ToPort=65535,
        )
print("[+] Security Group ID: "+security_group.id)

# Creating EC2 Instance
print("[*] Creating EC2 Instance")
instances = ec2.create_instances(
  ImageId='ami-00db12b46ef5ebc36',
  NetworkInterfaces=[{'SubnetId':subnet.id,'DeviceIndex':0,'AssociatePublicIpAddress':True,'Groups':[security_group.group_id]}],
  MinCount=1,
  MaxCount=1,
  InstanceType='t2.micro',
  KeyName='[UPDATE_THIS_WITH_YOUR_KEY]')
instances[0].wait_until_running()
instance_ = list(ec2.instances.filter(InstanceIds=[instances[0].id]))
print("[+] EC2 Instance Public Ip Address: "+instance_[0].network_interfaces[0].association_attribute['PublicIp'])
print("[+] EC2 Instance ID: "+instances[0].id)
pub_ip = instance_[0].network_interfaces[0].association_attribute['PublicIp']
priv_ip = instance_[0].private_ip_address
# Creating DNS Route53 Records
print("[*] Creating DNS Route53 Records")
r = r53.create_hosted_zone(
        Name=domain_name,

        CallerReference=str(datetime.today()),

        )
zones = r53.list_hosted_zones_by_name(DNSName=domain_name)
zone_id = zones['HostedZones'][0]['Id'][12:]
print("[+] Hosted Zone ID: "+zone_id)
response = r53.change_resource_record_sets(
    HostedZoneId=zone_id,
    ChangeBatch={
        'Comment': 'Create dns entry',
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': 'ns1.'+domain_name,
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [
                      {
                      'Value': pub_ip
                      },],
                }
            },
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': '*.'+domain_name,
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [
                      {
                      'Value': pub_ip
                      },],
                }
            },
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': domain_name,
                    'Type': 'NS',
                    'TTL': 300,
                    'ResourceRecords': [
                      {
                      'Value': 'ns1.'+domain_name+'.',
                      },],
                }
            },
        ]
    }
)
# Upading BurpSuite Collaborator Configuration file [make sure you download it]
print("[*] Upading the Configuration BurpSuite file")
fin = open("burp.config.bak", "rt")
data = fin.read()
data = data.replace('DOMAIN', domain_name)
data = data.replace('LOCALIP',priv_ip )
data = data.replace('PUBLICIP', pub_ip)
fin.close()

fin = open("burp.config", "wt")
fin.write(data)
fin.close()
