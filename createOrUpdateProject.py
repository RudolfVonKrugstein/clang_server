import projectDatabase
import os

filePath = os.path.abspath('./file')
if filePath != "":
  root = projectDatabase.createOrUpdateProjectForFile(filePath, [], {})
