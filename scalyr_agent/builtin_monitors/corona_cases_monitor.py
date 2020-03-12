from __future__ import unicode_literals
from __future__ import absolute_import

if False:
    from typing import Dict

import six
import six.moves.urllib.request
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.http_cookiejar
import six.moves.http_client

from lxml import html

from scalyr_agent import ScalyrMonitor, define_config_option, define_metric

__monitor__ = __name__

define_config_option(
    __monitor__,
    "module",
    "Always ``scalyr_agent.builtin_monitors.corona_monitor``",
    required_option=True,
)

define_config_option(
    __monitor__, "id", "corona_cases", convert_to=six.text_type,
)


define_config_option(__monitor__, "countries", [], required_option=True)

# Metric definitions.
define_metric(
    __monitor__, "corona.total_cases", "Total cases.", cumulative=False,
)

define_metric(
    __monitor__, "corona.total_deaths", "Total deaths.", cumulative=False,
)

define_metric(
    __monitor__, "corona.total_recovered", "Total recovered.", cumulative=False,
)

URL = "https://www.worldometers.info/coronavirus/"


class CoronaCasesMonitor(ScalyrMonitor):
    def _initialize(self):
        self._countries = self._config["countries"]

    def gather_sample(self):
        for country in self._countries:
            data = self._gather_sample_for_country(country=country)

            if not data:
                continue

            for metric_name, metric_value in data.items():
                extra = {"country": country.lower()}
                metric_name = "corona.%s" % (metric_name)
                self._logger.emit_value(metric_name, metric_value, extra)

    def _gather_sample_for_country(self, country):
        # type: (str) -> Dict[str, int]
        request = six.moves.urllib.request.Request(URL)
        opener = six.moves.urllib.request.build_opener(
            six.moves.urllib.request.HTTPCookieProcessor(
                six.moves.http_cookiejar.CookieJar()
            ),
        )

        try:
            response = opener.open(request, timeout=5)
            response_body = response.read()
            response.close()
        except Exception as e:
            self._logger.error("Failed to retrieve data: %s" % (str(e)))

        if response.code != 200 or b"Not Found" in response_body:
            # They don't return 404 status code on not found :/
            self._logger.error(
                "Server returned non-200 status code. body=%s,code=%s"
                % (response_body, response.code)
            )
            return None

        data = self._parse_response_body(country, response_body)
        return data

    def _parse_response_body(self, country, body):
        root = html.fromstring(body)

        # Country without a sub page
        tr_elems = root.xpath("//td[contains(text(),'%s')]/parent::tr" % (country))

        # Country with a subpage
        if not tr_elems:
            tr_elems = root.xpath(
                "//td/a[contains(text(),'%s')]/parent::td/parent::tr" % (country)
            )

        if not tr_elems:
            return

        tr_elem = tr_elems[0]
        td_elems = tr_elem.getchildren()

        total = td_elems[1].text
        dead = td_elems[4].text
        recovered = td_elems[6].text

        total = int(total.strip().replace(",", "") or 0)
        dead = int(dead.strip().replace(",", "") or 0)
        recovered = int(recovered.strip().replace(",", "") or 0)

        result = {
            "total_cases": total,
            "total_deaths": dead,
            "total_recovered": recovered,
        }

        return result
