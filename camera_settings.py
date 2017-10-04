#JUST RUN NORMALLY, CHANGE CAMERA PORT ACCORDINGLY 
import cv2
import argparse
from operator import xor

CAMERA_PORT = 0
def callback(value):
    pass


def setup_trackbars(range_filter):
    exposure = 10
    contrast = 50
    brightness = 10
    hue  = 10
    saturation  = 75


    cv2.namedWindow("Trackbars", 0)
    cv2.createTrackbar("Exposure", "Trackbars", exposure, 20, callback)
    cv2.createTrackbar("Contrast", "Trackbars", contrast, 100, callback)
    cv2.createTrackbar("Brightness", "Trackbars", brightness, 20, callback)
    cv2.createTrackbar("Hue", "Trackbars", hue, 20, callback)
    cv2.createTrackbar("Saturation", "Trackbars", saturation, 150, callback)

def get_trackbar_values():
    values = []
    v = cv2.getTrackbarPos("Exposure", "Trackbars")
    values.append(v)

    v = cv2.getTrackbarPos("Contrast", "Trackbars")
    values.append(v)

    v = cv2.getTrackbarPos("Brightness", "Trackbars")
    values.append(v)

    v = cv2.getTrackbarPos("Hue", "Trackbars")
    values.append(v)

    v = cv2.getTrackbarPos("Saturation", "Trackbars")
    values.append(v)

    return values
def setExposure(camera, v):
    newExp = -7 + ((int)(v-10))
    camera.set(15,newExp)
def setContrast(camera, v):
    newCon = 32 + ((int)(v-50))
    camera.set(11,newCon)
def setBrightness(camera, v):
    newBright = 0 + ((int)(v-10))
    camera.set(10,newBright)
def setHue(camera, v):
    newHue = 0 + ((int)(v-10))
    camera.set(13,newHue)
def setSaturation(camera, v):
    newSat = 60 + ((int)(v-75))
    camera.set(12,newSat)

def getValues(camera):
    exposure = str(camera.get(15))
    contrast = str(camera.get(11))
    brightness = str(camera.get(10))
    hue  = str(camera.get(13))
    saturation  = str(camera.get(12))
    print "Exposure,Contrast,Brightness,Hue,Saturation: {} ,{} ,{} ,{} ,{}".format(exposure,contrast,brightness,hue,saturation) 

def main():

    range_filter = "HSV"
    camera = cv2.VideoCapture(CAMERA_PORT)

    setup_trackbars(range_filter)

    while True:
        ret, image = camera.read()

        if not ret:
             break
        frame_to_thresh = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        exposure,contrast,brightness,hue,saturation = get_trackbar_values()
        setExposure(camera,exposure)
        setContrast(camera,contrast)
        setBrightness(camera,brightness)
        setHue(camera,hue)
        setSaturation(camera,saturation)
        getValues(camera)

        # new values
        greenLower = (31, 100, 65)
        greenUpper = (44, 195, 149)
        # blue
        # blueLower = (99, 60, 29)
        # blueUpper = (110, 255, 188)
        # red
        # redLower = (169, 84, 77)
        # redUpper = (179, 255, 255)
        thresh = cv2.inRange(frame_to_thresh, greenLower, greenUpper)

        cv2.imshow("Original", image)
        cv2.imshow("Thresh", thresh)

        if cv2.waitKey(1) & 0xFF is ord('q'):
            break


if __name__ == '__main__':
    main()