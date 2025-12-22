from . import user_dto as _user_dto
from . import pond_dto as _pond_dto
from . import task_dto as _task_dto
from . import feeding_dto as _feeding_dto
from . import water_quality_dto as _water_quality_dto
from . import growth_dto as _growth_dto
from . import alert_dto as _alert_dto
from . import report_dto as _report_dto
from . import fish_dto as _fish_dto
from . import pond_event_dto as _pond_event_dto
from . import company_dto as _company_dto

UserDTO = _user_dto.UserDTO
PondDTO = _pond_dto.PondDTO
StockRecordDTO = _pond_dto.StockRecordDTO
TaskDTO = _task_dto.TaskDTO
FeedingRecordDTO = _feeding_dto.FeedingRecordDTO
WaterQualityRecordDTO = _water_quality_dto.WaterQualityRecordDTO
GrowthRecordDTO = _growth_dto.GrowthRecordDTO
AlertDTO = _alert_dto.AlertDTO
ReportDTO = _report_dto.ReportDTO
FishDTO = _fish_dto.FishDTO
PondEventDTO = _pond_event_dto.PondEventDTO
CompanyDTO = _company_dto.CompanyDTO

__all__ = [
    'UserDTO', 'PondDTO', 'StockRecordDTO', 'TaskDTO', 'FeedingRecordDTO', 'WaterQualityRecordDTO', 'GrowthRecordDTO', 'AlertDTO', 'ReportDTO', 'FishDTO', 'PondEventDTO', 'CompanyDTO'
]
