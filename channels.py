class INPUT:
	PORT4          = 3
	OBSTRUCTION    = 0x300+23
	STOP           = 0x300+22
	FLOOR_COMMAND1 = 0x300+21
	FLOOR_COMMAND2 = 0x300+20
	FLOOR_COMMAND3 = 0x300+19
	FLOOR_COMMAND4 = 0x300+18
	FLOOR_UP1      = 0x300+17
	FLOOR_UP2      = 0x300+16

	PORT1          = 2
	FLOOR_DOWN1		= -1
	FLOOR_DOWN2    = 0x200+0
	FLOOR_UP3      = 0x200+1
	FLOOR_UP4 		= -1
	FLOOR_DOWN3    = 0x200+2
	FLOOR_DOWN4    = 0x200+3
	SENSOR1        = 0x200+4
	SENSOR2        = 0x200+5
	SENSOR3        = 0x200+6
	SENSOR4        = 0x200+7
	IN_BUTTONS = [FLOOR_COMMAND1, FLOOR_COMMAND2, FLOOR_COMMAND3, FLOOR_COMMAND4]
	UP_BUTTONS = [FLOOR_UP1, FLOOR_UP2, FLOOR_UP3, FLOOR_UP4]
	DOWN_BUTTONS = [FLOOR_DOWN1, FLOOR_DOWN2, FLOOR_DOWN3, FLOOR_DOWN4]

	BUTTONS = IN_BUTTONS + UP_BUTTONS + DOWN_BUTTONS + [STOP]

	SENSORS = [SENSOR1, SENSOR2, SENSOR3, SENSOR4]

	ALL = BUTTONS + SENSORS + [OBSTRUCTION]

	NUM_FLOORS = len(SENSORS)

class OUTPUT:
	PORT3          = 3
	MOTORDIR       = 0x300+15
	LIGHT_STOP     = 0x300+14
	LIGHT_COMMAND1 = 0x300+13
	LIGHT_COMMAND2 = 0x300+12
	LIGHT_COMMAND3 = 0x300+11
	LIGHT_COMMAND4 = 0x300+10
	LIGHT_UP1      = 0x300+9
	LIGHT_UP2      = 0x300+8

	PORT2          = 3
	LIGHT_DOWN1		= -1
	LIGHT_DOWN2    = 0x300+7
	LIGHT_UP3      = 0x300+6
	LIGHT_UP4		= -1
	LIGHT_DOWN3    = 0x300+5
	LIGHT_DOWN4    = 0x300+4
	DOOR_OPEN      = 0x300+3
	FLOOR_IND1     = 0x300+1
	FLOOR_IND2     = 0x300+0

	PORT0          = 1
	MOTOR          = 0x100+0

	MOTOR_UP       = 0
	MOTOR_DOWN     = 1
	UP_LIGHTS = [LIGHT_UP1, LIGHT_UP2, LIGHT_UP3, LIGHT_UP4]
	DOWN_LIGHTS = [LIGHT_DOWN1, LIGHT_DOWN2, LIGHT_DOWN3, LIGHT_DOWN4]
	IN_LIGHTS = [LIGHT_COMMAND1, LIGHT_COMMAND2, LIGHT_COMMAND3, LIGHT_COMMAND4]
	FLOOR_LIGHTS = [FLOOR_IND1, FLOOR_IND2]
	LIGHTS = UP_LIGHTS + DOWN_LIGHTS

	ALL = LIGHTS + [MOTOR, MOTORDIR]