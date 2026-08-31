CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c11
TARGET  = simulator

all: $(TARGET)

$(TARGET): simulator.c
	$(CC) $(CFLAGS) -o $(TARGET) simulator.c

clean:
	rm -f $(TARGET) *.o

.PHONY: all clean
