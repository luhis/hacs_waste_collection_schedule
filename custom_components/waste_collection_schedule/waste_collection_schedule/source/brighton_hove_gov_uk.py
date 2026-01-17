import logging
import re
import time
from datetime import datetime

import requests
from waste_collection_schedule import Collection  # type: ignore[attr-defined]
from waste_collection_schedule.exceptions import SourceArgumentNotFound

TITLE = "Brighton and Hove City Council"
DESCRIPTION = "Source for Brighton and Hove City Council."
URL = "https://www.brighton-hove.gov.uk/"
TEST_CASES = {
    "BN1 1TZ, 22209581": {"postcode": "BN11TZ", "uprn": "22209581"},
    "BN2 1RW, 22121043": {"postcode": "BN2 1RW", "uprn": 22121043},
}
_LOGGER = logging.getLogger(__name__)


ICON_MAP = {
    "Maroon": "mdi:trash-can",
    "Grey": "mdi:recycle",
    "Blue": "mdi:leaf",
}

BASE_URL = "https://enviroservices.brighton-hove.gov.uk/"
INIT_URL = f"{BASE_URL}link/collections"
API_URL = f"{BASE_URL}xas/"

INIT_PAYLOAD = {
    "action": "get_session_data",
    "params": {
        "hybrid": False,
        "offline": False,
        "referrer": None,
        "profile": "",
        "timezoneoffset": 0,
        "timezoneId": "Europe/London",
        "preferredLanguages": ["en-GB", "en-US", "en"],
        "version": 2,
    },
}


class Source:
    def __init__(self, postcode: str, uprn: str | int):
        self._postcode: str = postcode
        self._uprn: str | int = uprn
        self._request_id = 3

    def _do_request(
        self,
        s: requests.Session,
        action: str,
        x_csrf_token: str,
        changes: dict = {},
        objects: list = [],
        params: dict[str, str | list[str] | dict] = {},
        profile_data: dict[str, int] = {},
        operation_id: str | None = None,
        validation_guids: list[str] | None = None,
    ) -> dict:
        time_str = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "x-csrf-token": x_csrf_token,
            "x-mx-reqtoken": time_str + "-" + str(self._request_id),
        }
        self._request_id += 1

        payload = {
            "action": action,
            "changes": changes,
            "objects": objects,
            "params": params,
            "profiledata": profile_data,
        }
        if operation_id:
            payload["operationId"] = operation_id
        if validation_guids:
            payload["validationGuids"] = validation_guids

        r = s.post(API_URL, json=payload, headers=headers)
        if r.status_code != 200:
            _LOGGER.error("error doing request: " + r.text)
        r.raise_for_status()
        return r.json()

    def fetch(self) -> list[Collection]:
        self._request_id = 3
        s = requests.Session()
        r = s.get(INIT_URL)
        r.raise_for_status()

        r = s.post(API_URL, json=INIT_PAYLOAD)
        r.raise_for_status()

        init_data = r.json()

        objects = [init_data["objects"][1]]
        # params: dict[str, str | list[str] | dict] = {
        #     "actionname": "Service_YouAreBeingRedirected.SUB_YouAreBeingRedirected",
        #     "applyto": "selection",
        #     "guids": [init_data["objects"][1]["guid"]],
        # }
        x_csrf_token = init_data["csrftoken"]
        cachebust = init_data["cachebust"]

        # data = self._do_request(
        #     s,
        #     action="executeaction",
        #     x_csrf_token=x_csrf_token,
        #     objects=objects,
        #     params=params,
        # )

        r = requests.get(
            BASE_URL + "pages/en_GB/BartecCollective/Jobs_Get_Combined.page.xml?" +
            cachebust,
            params={cachebust: ""},
        )
        r.raise_for_status()

        # OPERATION_ID_REGEX = r'"config":{"operationId":"([a-zA-Z0-9/]+)",'
        OPERATION_ID_REGEX = r'"config":{"operationId":"(.+?)",'
        operation_ids = list(re.finditer(OPERATION_ID_REGEX, r.text))
        operation_id_post = operation_ids[0].group(1)
        operation_id_uprn = operation_ids[1].group(1)

        # objects = data["objects"]
        changes_postcode = init_data["changes"]
        changes_postcode[list(changes_postcode.keys())[0]][
            "SearchString"
        ] = {"value": self._postcode}
        # changes_postcode = [{"SearchString": {"value": self._postcode}}]

        guid = init_data["objects"][2]["guid"]
        params = {
            "Address": {
                "guid": guid,
            }
        }
        validation_guids = list(changes_postcode.keys())

        data = self._do_request(
            s,
            action="runtimeOperation",
            x_csrf_token=x_csrf_token,
            objects=objects,
            changes=changes_postcode,
            operation_id=operation_id_post,
            params=params,
            validation_guids=validation_guids,
        )

        uprn_chage_element: tuple[str, dict] | None = None

        for change_id, chage_dict in data["changes"].items():
            if "UPRN" in chage_dict and chage_dict["UPRN"]["value"].strip().strip(
                "0"
            ) == str(self._uprn).strip().strip("0"):
                uprn_chage_element = (change_id, chage_dict)
                break

        if uprn_chage_element is None:
            raise SourceArgumentNotFound("uprn", self._uprn)

        objects += [
            next(
                iter([o for o in data["objects"]
                     if o["guid"] == uprn_chage_element[0]])
            )
        ]
        params = {"Generic_Address": {"guid": objects[-1]["guid"]}}

        changes = changes_postcode.copy()
        changes[list(changes.keys())[0]]["ShowAddressResults"] = {
            "value": True}

        changes.update({uprn_chage_element[0]: uprn_chage_element[1]})
        data = self._do_request(
            s,
            "runtimeOperation",
            changes=changes,
            objects=objects,
            operation_id=operation_id_uprn,
            x_csrf_token=x_csrf_token,
            validation_guids=validation_guids,
            params=params,
        )

        entries = []
        for change in data["changes"].values():
            for key, value in change.items():
                if not key.startswith("Next"):
                    continue
                # Tuesday 07/01/2025
                date_str = value["value"]
                bin_type = key.replace("Next", "")
                try:
                    date = datetime.strptime(date_str, "%A %d/%m/%Y").date()
                except ValueError:
                    _LOGGER.warning(
                        f"Could not parse date: {date_str} for bin type {bin_type}"
                    )
                icon = ICON_MAP.get(bin_type)
                entries.append(Collection(date=date, t=bin_type, icon=icon))

        return entries
