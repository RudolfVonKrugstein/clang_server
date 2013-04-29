import projectDatabase
import os

filePath = os.path.abspath('./file')
if filePath != "":
  projectDatabase.getLoadOrCreateFilesProject(filePath)
