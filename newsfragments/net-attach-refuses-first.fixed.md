`phoxtail net attach` refuses a project name another project already uses
before it creates the shared Docker network, so a refused attach no longer
leaves a new network behind.
