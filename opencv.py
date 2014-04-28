"""Robot OpenCV and Controller Script

Retrieve camera information from stream
Communicates through sockets with a websocket server
Applies OpenCV algorithms through video stills
OpenCV results through the socket
Receives robot commands from socket

"""

import io
import socket
import struct
import datetime
import time
import numpy as np
import cv2
import urllib2
from optparse import OptionParser

# Class to store opencv cascade classifier details
class PiCV:
    cascade = None;
    color = (255,0,0)
    x = 0
    y = 0
    w = 0
    h = 0
    #Expects a valid classifier file, color tuple
    def __init__(self, cascade_file, color):
        #self.classifier = cv2.CascadeClassifier(cascade_file)
        self.color = color

    #Use a grayscale image for better results
    def detect_classifier(base_image):
        objects = self.cascade.detectMultiScale(gray, 1.3, 5)
        return objects

cascades = [
    #PiCV('cascade_files/lbpcascade_frontalface.xml', (255,0,0)),
    #PiCV('cascade_files/haarcascade_fullbody.xml', (0,255,0)),
    #PiCV('cascade_files/haarcascade_upperbody.xml', (0,0,255)),
    PiCV('cascade_files/haarcascade_mcs_upperbody.xml', (0,255,255)),
]

CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240
COLOR_FOCUS = (255,255,0)
face_cascade = cv2.CascadeClassifier('cascade_files/lbpcascade_frontalface.xml')
body_cascade = cv2.CascadeClassifier('cascade_files/haarcascade_fullbody.xml')
upper_cascade = cv2.CascadeClassifier('cascade_files/haarcascade_upperbody.xml')
upper2_cascade = cv2.CascadeClassifier('cascade_files/haarcascade_mcs_upperbody.xml')

#general
run_loop = True
server_address = 'http://127.0.0.1'
server_port = 8000
stream = io.BytesIO()
robot_status = {}
user_commands = []
after_image = '';

#command line arguments
parser = OptionParser()
parser.add_option("-s", "--server", dest="server",
    help="address of the server to send opencv data to")
parser.add_option("-p", "--port", dest="port",
    help="port socket will use")

(options, args) = parser.parse_args()
#server address
if options.server:
    server_address = options.server
if options.port:
    server_port = options.port

# Start a socket listening for connections on 0.0.0.0:8000 (0.0.0.0 means
# all interfaces)
server_socket = socket.socket()
server_socket.bind(('0.0.0.0', server_port))
server_socket.listen(0)

# Accept a single connection and make a file-like object out of it
connection = server_socket.accept()[0].makefile('rb')

def detect_face(raw_image):
    notFound = True
    robot_status ['General'] = 'No face found'
    after_image = raw_image
    gray = cv2.cvtColor(raw_image,cv2.COLOR_BGR2GRAY)
    
    for cascade in cascades:
        objects = cascade.cascade.detect_classifier(gray)
        for (x,y,w,h) in objects:
            if (notFound):
                cv2.rectangle(after_image,(x,y),(x+w,y+h),COLOR_FOCUS,2)
                move_command(x, y, w, h)
                notFound = False
            else:
                cv2.rectangle(after_image,(x,y),(x+w,y+h),cascade.color,2)
    
    return after_image

#generate movement command based on cascade detection box properties
def move_command(x, y, w, h):
    offCenter = x + w/2.0 - CAMERA_WIDTH/2.0
    print "({0}, {1}) {2}x{3}".format(x,y,w,h)
    print 'Off Center: ' + str(offCenter)
    robot_status ['General'] = 'Face found'
    robot_status ['Face Center X'] = 'X: ' + str(x + w/2)
    robot_status ['Face Center Y'] = 'Y: ' + str(y + h/2)
    robot_status ['Face Off Center'] = str(offCenter)
    
    off_center_percent = offCenter / CAMERA_WIDTH
    
    if abs(off_center_percent) > 0.01:
        turn_amount = off_center_percent * 150.0 + 75
        print offCenter
        print off_center_percent
        user_commands.append('manual-turn-' + str(turn_amount))
        robot_status ['Direction'] = 'Turning to: ' + str(turn_amount)
    else:
        user_commands.append('manual-turn-neutral')
        robot_status ['Direction'] = 'Neutral'
    
    #Adjust acceleration based on face box width
    if w < 70 and w > 40:
        #user_commands.append('manual-throttle-forward')
        move_for = (70 - w)
        user_commands.append('manual-throttle-forward-'+str(move_for))
        robot_status ['Movement'] = 'Forward'
    elif w > 120:
        user_commands.append('manual-throttle-reverse')
        robot_status ['Movement'] = 'Reverse'
    else:
        user_commands.append('manual-throttle-stop')
        robot_status ['Movement'] = 'None'

# ----- Main Operation -----
try:
    while run_loop:
        user_commands = []
        robot_status = {'Timestamp': str(datetime.datetime.now())}
        robot_status ['Has Camera'] = True
        # Read the length of the image as a 32-bit unsigned int. If the
        # length is zero, quit the loop
        image_len = struct.unpack('<L', connection.read(4))[0]
        if not image_len:
            print 'not image_len'
            continue
        # Construct a stream to hold the image data and read the image
        # data from the connection
        image_stream = io.BytesIO()
        image_stream.write(connection.read(image_len))
        # Rewind the stream, open it as an image with PIL and do some
        # processing on it
        image_stream.seek(0)
        data = np.fromstring(image_stream.getvalue(), dtype=np.uint8)
        image = cv2.imdecode(data, 1)
        
        new_image = detect_face(image)
        
        # Display the resulting frame
        cv2.imshow('camera',new_image)
        print('Image is processed')
        for command in user_commands:
            response = urllib2.urlopen(server_address+'/command/?command='+command).read()
            print response
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    connection.close()
    server_socket.close()
    cv2.destroyAllWindows()