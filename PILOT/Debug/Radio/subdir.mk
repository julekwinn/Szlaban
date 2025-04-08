################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Radio/board.c \
../Radio/delay.c \
../Radio/gpio-board.c \
../Radio/gpio.c \
../Radio/rtc-board.c \
../Radio/spi-board.c \
../Radio/sx1276-board.c \
../Radio/timer.c \
../Radio/utilities.c 

OBJS += \
./Radio/board.o \
./Radio/delay.o \
./Radio/gpio-board.o \
./Radio/gpio.o \
./Radio/rtc-board.o \
./Radio/spi-board.o \
./Radio/sx1276-board.o \
./Radio/timer.o \
./Radio/utilities.o 

C_DEPS += \
./Radio/board.d \
./Radio/delay.d \
./Radio/gpio-board.d \
./Radio/gpio.d \
./Radio/rtc-board.d \
./Radio/spi-board.d \
./Radio/sx1276-board.d \
./Radio/timer.d \
./Radio/utilities.d 


# Each subdirectory must supply rules for building sources it contributes
Radio/%.o Radio/%.su Radio/%.cyclo: ../Radio/%.c Radio/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m33 -std=gnu11 -g3 -DDEBUG -DUSE_MODEM_FSK -DUSE_HAL_DRIVER -DSTM32U545xx -c -I../Core/Inc -I"C:/Users/julek/Desktop/STM32CubeExpansion_Crypto_V4.4.0/Middlewares/ST/STM32_Cryptographic/include" -I"D:/MGR/BEKO_PROJEKT/Projekt/Radio" -I../Drivers/STM32U5xx_HAL_Driver/Inc -I../Drivers/STM32U5xx_HAL_Driver/Inc/Legacy -I../Drivers/CMSIS/Device/ST/STM32U5xx/Include -I../Drivers/CMSIS/Include -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv5-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Radio

clean-Radio:
	-$(RM) ./Radio/board.cyclo ./Radio/board.d ./Radio/board.o ./Radio/board.su ./Radio/delay.cyclo ./Radio/delay.d ./Radio/delay.o ./Radio/delay.su ./Radio/gpio-board.cyclo ./Radio/gpio-board.d ./Radio/gpio-board.o ./Radio/gpio-board.su ./Radio/gpio.cyclo ./Radio/gpio.d ./Radio/gpio.o ./Radio/gpio.su ./Radio/rtc-board.cyclo ./Radio/rtc-board.d ./Radio/rtc-board.o ./Radio/rtc-board.su ./Radio/spi-board.cyclo ./Radio/spi-board.d ./Radio/spi-board.o ./Radio/spi-board.su ./Radio/sx1276-board.cyclo ./Radio/sx1276-board.d ./Radio/sx1276-board.o ./Radio/sx1276-board.su ./Radio/timer.cyclo ./Radio/timer.d ./Radio/timer.o ./Radio/timer.su ./Radio/utilities.cyclo ./Radio/utilities.d ./Radio/utilities.o ./Radio/utilities.su

.PHONY: clean-Radio

