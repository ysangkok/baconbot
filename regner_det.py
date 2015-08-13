import colorsys
import requests
import sys
from PIL import Image
from io import BytesIO
import itertools

def chunks(iterable,size):
    """ http://stackoverflow.com/a/434314/309483 """
    it = iter(iterable)
    chunk = tuple(itertools.islice(it,size))
    while chunk:
        yield chunk
        chunk = tuple(itertools.islice(it,size))

def getimg():
    data = requests.get("http://www.wetteronline.de/?ireq=true&pid=p_radar_forecast&src=radar/vermarktung/p_radar_map_forecast/forecastLoop/DL/latestForecastLoop.gif", stream=True)
    return Image.open(BytesIO(data.raw.data))

def get_pixels_in_all_frames(im):
  try:
      while 1:
          im.seek(im.tell()+1)
          # do something to im
          for x in range(520):
               for y in range(571):
                    yield im.load()[x,y]
  except EOFError:
      pass # end of sequence

def countblue(im):
  for idx, i in enumerate(chunks(get_pixels_in_all_frames(im), 4)):
    hsv = colorsys.rgb_to_hsv(r=i[0], g=i[1], b=i[2])
    assert i[3] == 0
    if 120 <= hsv[0] <= 360:
      yield 1

def get_weather():
  im = getimg()
  number_of_frames = 1
  try:
      while 1:
          im.seek(im.tell()+1)
          number_of_frames += 1
  except EOFError:
      pass # end of sequence
  fraction = sum(countblue(im)) / 520*571*number_of_frames
  if fraction > 0.5:
      return fraction
  else:
      return None

if __name__=="__main__":
  print(get_weather())
