# Class for console menu, for testing the client
class Menu:
  items = []

  class Item:
    def __init__(self, text, func):
      self.text = text
      self.do = func

  def addItem(self,text,func):
    self.items.append(Menu.Item(text,func))

  def display(self):
    for i in xrange(len(self.items)):
      print (str(i+1) + ")"),self.items[i].text
    print "0) Quit"

  def run(self):
    quit = False
    while(not quit):
      self.display()
      n=raw_input("choice> ")
      try:
        n = int(n)
        if n == 0:
          quit = True
        else:
          if n-1 < len(self.items):
            try:
              self.items[n-1].do()
            except Exception,e:
              print "Command throw exception:",e
      except:
        print "Please enter a number!"
