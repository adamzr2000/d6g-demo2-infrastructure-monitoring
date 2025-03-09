#!/bin/bash

# Assemble docker image. 
echo 'Building kafka-agent docker image.'
sudo docker build . -t kafka-agent