#!/usr/bin/env python3

from pywot import (
    WoTThing,
    log_config
)
from configman import (
    configuration,
    Namespace,
    class_converter,
    RequiredConfig,
)
import asyncio
import aiohttp
import async_timeout
import json
import logging


def create_url(config, local_namespace, args):
    """generate a URL to fetch local weather data from Weather Underground using
    configuration data"""
    return "http://api.wunderground.com/api/{}/conditions/q/{}/{}.json".format(
        config.weather_underground_api_key,
        config.state_code,
        config.city_name
    )


class WeatherStation(WoTThing, RequiredConfig):
    required_config = Namespace()
    required_config.add_option(
        'weather_underground_api_key',
        doc='the api key to access Weather Underground data',
        short_form="K",
        default="not a real key"
    )
    required_config.add_option(
        'state_code',
        doc='the two letter state code',
        default="OR",
    )
    required_config.add_option(
        'city_name',
        doc='the name of the city',
        default="Corvallis",
    )
    required_config.add_aggregation(
        'target_url',
        function=create_url
    )
    required_config.add_option(
        'seconds_for_timeout',
        doc='the number of seconds to allow for fetching weather data',
        default=10
    )

    def __init__(
        self,
        config,
        name='my_weatherstation',
        type_='thing',
        description='a weather station'
    ):
        super(WeatherStation, self).__init__(config, name, type_, description)
        self.fallback_weather_data = {
            'current_observation': {
                'temp_f': 0,
                'pressure_in': 0,
                'wind_mph': 0,
            }
        }
        self.weather_data = {}

    async def get_weather_data(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(config.seconds_for_timeout):
                    async with session.get(config.target_url) as response:
                        self.fallback_weather_data = self.weather_data
                        self.weather_data = json.loads(await response.text())
        except asyncio.CancelledError as e:
            raise e
        except Exception as e:
            logging.critical('loading weather data fails: %s', e)
            self.weather_data = self.fallback_weather_data
        self.temperature = self.weather_data['current_observation']['temp_f']
        self.barometric_pressure = self.weather_data['current_observation']['pressure_in']
        self.wind_speed = self.weather_data['current_observation']['wind_mph']

    temperature = WoTThing.wot_property(
        name='temperature',
        initial_value=0,
        description='the temperature in ℉',
        value_source_fn=get_weather_data,
        metadata = {
            'units': '℉'
        }
    )
    barometic_pressure = WoTThing.wot_property(
        name='barometric_pressure',
        initial_value=30,
        description='the air pressure in inches',
        metadata={
            'units': 'in'
        }
    )
    wind_speed = WoTThing.wot_property(
        name='wind_speed',
        initial_value=30,
        description='the wind speed in mph',
        metadata={
            'units': 'mph'
        }
    )


def run_server(config):
    logging.debug('run server')

    weather_station = config.weather_station_class(config)

    server = config.server.wot_server_class(
        config,
        [weather_station],
        port=config.server.service_port
    )
    server.run()


if __name__ == '__main__':
    required_config = Namespace()
    required_config.server = Namespace()
    required_config.server.add_option(
        name='wot_server_class',
        default="pywot.WoTServer",
        doc="the fully qualified name of the WoT Server class",
        from_string_converter=class_converter
    )
    required_config.add_option(
        name="weather_station_class",
        default=WeatherStation,
        doc="the fully qualified name of the WoT weather station class",
        from_string_converter=class_converter
    )
    required_config.add_option(
        'logging_level',
        doc='log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)',
        default='INFO',
        from_string_converter=lambda s: getattr(logging, s.upper(), None)
    )
    required_config.add_option(
        'logging_format',
        doc='format string for logging',
        default='%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s',
    )

    config = configuration(required_config)
    logging.basicConfig(
        level=config.logging_level,
        format=config.logging_format
    )
    log_config(config)
    run_server(config)
