import os, fnmatch

def find_files(directory, patterns):
  ''' Supporting function to iterate over all files
  recusivly in a directory which follow a specific pattern.'''
  for root, dirs, files in os.walk(directory):
    for basename in files:
      for pattern in patterns:
        if fnmatch.fnmatch(basename, pattern):
          filename = os.path.join(root, basename)
          yield filename

def find_cpp_files(path = "."):
  '''Iterate over all files which are cpp file'''
  return find_files(path,map (lambda ex: "*" + ex, cppExtensions))
cppExtensions = [".cpp",".cc"]

class ClangCompilationDatabase:
  '''More or less a fake compilation database. It simple searches for
     all cpp files and returns the same args for them (which it takes from the
     .clang_complete file).'''
  def __init__(self,rootDir):
    self.rootDir = rootDir
    f = open(os.path.join(rootDir,".clang_complete"))
    c = f.read()
    f.close()
    self.args = c.split("\n")

  def getCompileCommands(self,filename):
    '''Very simple because for all files the arguments are the same'''
    return self.args

  def getAllFiles(self):
    return find_cpp_files(self.rootDir)
