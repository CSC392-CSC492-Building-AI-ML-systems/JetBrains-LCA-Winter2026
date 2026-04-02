CC      = gcc
CFLAGS  = -Wall -Wextra -g -O0
LDFLAGS =

SRCS = main.c handlers.c utils.c auth.c
OBJS = $(SRCS:.c=.o)
TARGET = logserver

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.c server.h
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
