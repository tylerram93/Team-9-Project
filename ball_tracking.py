from collections import deque
import numpy as np
import math
import argparse
import imutils
import cv2
import serial
import time
import threading
# import bluetooth
import socket_client as client

# define globals
DEBUG = True
PORT = 'COM8' # COM8 USB3.0 Kangaroo
GAMMA = 0.5
# SERVER_IP = "localhost" #don't need
# directions
FORWARD = 0
REVERSE = 1
RIGHT = 2
LEFT = 3
# speeds
SLOW = 0
FAST = 1
HALT = 2

# direction and speed constants
STOP = 0
FL = 1 # fast left
FF = 2 # fast forward
FR = 3 # fast right
FB = 4 # fast backwards
SL = 5 # slow left
SF = 6 # slow forward
SR = 7 # slow right
SB = 8 # slow backwards
NA = 9 # no ball, roam

# responses
L = 0
M = 1
R = 2
LM = 3
LR = 4
MR = 5
LRM = 6
NONE = 7

ball_missing_counter = 0	
ball_missing_max = 20	

# message format
MESSAGE_SEP = ','
MESSAGE_END = '!'
# horizontal calibration
frame_size = 600
frame_height = 450
horizontal_mid = frame_size / 2
dead_zone = 80
slow_zone = 600
# depth calibration
half_ft = 35
one_ft = 25
two_ft = 11.5
three_ft = 7.2
four_ft = 3.5
max_radius = 120 # rough estimate
# speed calibration
norm_speedL = 60
norm_speedR = 44

# keeping track of last position
last_center = (0,0)
last_radius = 0
last_command = NA
last_response = NONE

# socket global vars
server_sock = 0
client_sock = 0
SEARCH_STATE = 0
FOUND_STATE = 1
LEADER_STATE = 2

CURR_STATE = SEARCH_STATE
BALL_FOUND = False
tracking_counter = 0
ROBOT_NUM = 10
robot_states = [0] * ROBOT_NUM
STOP_FLAG = False
STOP_TIMEOUT = 5
CAN_SEND_STOP = True

def start_moving():
	global STOP_FLAG
	dprint("continue searching")
	STOP_FLAG = False

def allow_sending():
	global CAN_SEND_STOP
	CAN_SEND_STOP = True
	
def dprint(string):
	global DEBUG
	if DEBUG:
		print(string)

def send_to_arduino(command, serial_port):
	# dprint("Sending %d to Arduino" % command)
	serial_port.write(b'%s' % command)

def get_response(serial_port):
	response = int(serial_port.readline())
	# response = 12
	# dprint("Arduino responded %d" % response)
	return response

def send_simple_command(center, radius, serial_port, frame):
	global last_center
	global last_radius
	global last_command
	global last_response
	global ball_missing_counter
	global ball_missing_max
	global BALL_FOUND
	global CURR_STATE
	command = NA
	valid_position = False

	color = (0,255,0) # green
	distance = math.sqrt((center[0] - last_center[0])**2 + \
		(center[1] - last_center[1])**2)
	#1st case: probably not our tennis ball
	#2nd case: bottom right corner is invalid
	#3rd case: inconsistent (jumping) frames
	if (center[1] < frame_height/3 or radius > max_radius) or  \
		(center[0] > 500 and center[1] > 300) or \
		(BALL_FOUND and (distance > 100 or math.fabs(radius - last_radius)) > 40):  
		command = last_command
		color = (0,0,255) # red
		if last_command != NA:
			ball_missing_counter += 1
	elif ((center[0] >= horizontal_mid - dead_zone/2) and \
		(center[0] <= horizontal_mid + dead_zone/2)):
		if (radius > one_ft):
			command = STOP # close enough
			if CURR_STATE != FOUND_STATE:
				client.send_found()
				dprint("We're in the found state!")
			CURR_STATE = FOUND_STATE
		elif (radius > two_ft):
			if CURR_STATE != FOUND_STATE:
				client.send_found()
				dprint("We're in the found state!")
			command = SF
		elif (radius <= two_ft):
			command = FF
		else:
			command = SF
		valid_position = True
	elif (center[0] < horizontal_mid - dead_zone/2):
		if (center[0] < horizontal_mid - slow_zone/2):
			command = FL
		elif (center >= horizontal_mid - slow_zone/2):
			command = SL
		else:	
			command = SL
		valid_position = True
	elif (center[0] > horizontal_mid + dead_zone/2):
		if (center[0] > horizontal_mid + slow_zone/2):
			command = FR
		elif (center[0] <= horizontal_mid + slow_zone/2):
			command = SR
		else:
			command = SR
		valid_position = True
	if ball_missing_counter >= ball_missing_max: # lost the ball so start surveying again
		command = NA
		BALL_FOUND = False
		CURR_STATE = SEARCH_STATE
		dprint("SENDING STOP")
		client.send_stop()
		ball_missing_counter = 0
		tracking_counter = 0
	elif valid_position:
		ball_missing_counter = 0
		# CURR_STATE = FOUND_STATE
	last_center = center
	last_radius = radius
	last_command = command

	if (center[0] != 0 and center[1] != 0):
		cv2.circle(frame, center, 5, color, -1)

	# Added for STOP_FLAG command
	if(STOP_FLAG):
		command = STOP
	
	send_to_arduino(command, serial_port)
	response = get_response(serial_port)

	# if (response == NONE and last_response != NONE and valid_position):
	# 	command = SB
	# 	send_to_arduino(command, serial_port)
	# 	time.sleep(1)
	# 	response = get_response(serial_port)
	# 	if (last_response == L or last_response == LM):
	# 		command = SR
	# 		send_to_arduino(command, serial_port)
	# 		time.sleep(1)
	# 		response = get_response(serial_port)
	# 		command = SF
	# 		send_to_arduino(command, serial_port)
	# 		time.sleep(2)
	# 		response = get_response(serial_port)
	# 		command = SL
	# 	elif (last_response == R or last_response == MR):
	# 		command = SL
	# 		send_to_arduino(command, serial_port)
	# 		time.sleep(1)
	# 		response = get_response(serial_port)
	# 		command = SF
	# 		send_to_arduino(command, serial_port)
	# 		time.sleep(2)
	# 		response = get_response(serial_port)
	# 		command = SR
	# 	else:
	# 		command = SF
	# 	last_command = command
	last_response = response

def connect_to_arduino(ard_port):
	connected = False
	while not connected:
		try:
			s = serial.Serial(port=ard_port, baudrate=9600)
			connected = True
		except serial.serialutil.SerialException:
			print("Connecting to Arduino...")
			time.sleep(1)
	return s

def adjust_gamma(image, gamma=0.5):
	# build a lookup table mapping the pixel values [0, 255] to
	# their adjusted gamma values
	invGamma = 1.0 / gamma
	table = np.array([((i / 255.0) ** invGamma) * 255
		for i in np.arange(0, 256)]).astype("uint8")
 
	# apply gamma correction using the lookup table
	return cv2.LUT(image, table)

def main():
	global CURR_STATE
	global CAN_SEND_STOP
	global STOP_FLAG
	global robot_states
	s = connect_to_arduino(PORT)
	print("Connected to Arduino!")
	client.handshake("9", SERVER_IP)
	# open_sockets()
	# server_sock.setblocking(False)
	# client_sock.setblocking(False)
	
	# s = None # if we want to fake send data

	# H = [0,179], S = [0,255], V = [0,255]

	# previous values
	# greenLower = (29, 86, 6)
	# greenLower = (29, 86, 30) # tighter
	# greenUpper = (64, 255, 255)

	# connors room
	# greenLower = (16, 171, 14)
	# greenUpper = (24, 241, 210)

	# new values
	greenLower = (31, 100, 65)
	greenUpper = (44, 195, 149)
	# blue
	# blueLower = (99, 60, 29)
	# blueUpper = (110, 255, 188)
	# red
	# redLower = (169, 84, 77)
	# redUpper = (179, 255, 255)
	
	camera = cv2.VideoCapture(0)
	camera.set(15, -7) # exposure -7 lab, -3 connor's room , 5 for hallway
	camera.set(11, 6) # contrast
	camera.set(10, 10) 	# brightness
	camera.set(13, 0) 	# hue
	camera.set(12, 58)	# saturation
	tracking_counter = 0
	STOP_FLAG = False

	##
	#while True:
	#	try:
	#		data = client.recv()
	#		if data != None:
	#			# dprint("recv'd data: %s" % str(data))
	#			dprint("curr state: %s" % str(CURR_STATE))
	#			# ignore command if found or leader
	#			for msg in data:
	#				print(str(msg))
	#				team_no = int(msg[0])
	#				cmd = msg[1]
	#				print("Recv'd %s from Team %d" % (cmd, team_no))
	#				if(CURR_STATE == SEARCH_STATE and cmd == client.STOP):
	#					STOP_FLAG = True
	#					# print("Waiting for %d seconds" % STOP_TIMEOUT)
	#					threading.Timer(STOP_TIMEOUT, start_moving).start()
	#					# time.sleep(STOP_TIMEOUT)
	#					# print('woke up')
	#					robot_states[team_no - 1] = SEARCH_STATE
	#				if(cmd == client.FOUND):
	#					robot_states[team_no] = FOUND_STATE
	#					if (CURR_STATE == FOUND_STATE):
	#						client.send_found()
	#			found_ct = 0
	#			for robot in robot_states:
	#				if robot == FOUND_STATE:
	#					found_ct += 1
	#			if found_ct == ROBOT_NUM - 1:
	#				CURR_STATE = LEADER_STATE
	#	except Exception as e:
	#		print(str(e))
	#		pass
	#
	(grabbed, frame) = camera.read()

	frame = imutils.resize(frame, width=frame_size)
	# frame = adjust_gamma(frame, GAMMA)
	# blurred = cv2.GaussianBlur(frame, (11, 11), 0)
	hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

	# construct a mask for the color "green", then perform
	# a series of dilations and erosions to remove any small
	# blobs left in the mask
	mask = cv2.inRange(hsv, greenLower, greenUpper)
	mask = cv2.erode(mask, None, iterations=2)
	mask = cv2.dilate(mask, None, iterations=2)

	# find contours in the mask and initialize the current
	# (x, y) center of the ball
	cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE)[-2]
	center = None
	# only proceed if at least one contour was found


	if len(cnts) > 0:
		# find the largest contour in the mask, then use
		# it to compute the minimum enclosing circle and
		# centroid
		c = max(cnts, key=cv2.contourArea)
		((x, y), radius) = cv2.minEnclosingCircle(c)
		M = cv2.moments(c)
		center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
		send_simple_command(center, radius, s, frame)
		tracking_counter += 1
		# only proceed if the radius meets a minimum size
		if radius > 3:
			# draw the circle and centroid on the frame,
			# then update the list of tracked points
			cv2.circle(frame, (int(x), int(y)), int(radius),
				(0, 255, 255), 2)
			# cv2.circle(frame, center, 5, (0, 0, 255), -1)
	else:
		# print("no contours found")
		send_simple_command((0,0), 200, s, frame)
	if tracking_counter >= 5 and CURR_STATE == SEARCH_STATE:
		BALL_FOUND = True
		if CAN_SEND_STOP:
			print("SENDING STOP")
			client.send_stop() # tell everyone else to stop moving so we can catch up
		CAN_SEND_STOP = False
		threading.Timer(STOP_TIMEOUT, allow_sending)

	# show the frame to our screen
	global DEBUG
	if DEBUG:
		cv2.imshow('frame', frame)
		cv2.imshow('mask', mask)
	#if cv2.waitKey(1) & 0xFF == ord('q'):
	#break
	#cleanup the camera and close any open windows
	camera.release()
	cv2.destroyAllWindows()

print("starting up")
main()