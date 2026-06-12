"""审核 Service — DraftProcessGraph → ApprovedProcessGraph (03_ARCHITECTURE.md §1.2)。"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ApprovedProcessGraph, ReviewDecision
from ..models.schemas import (
    ApprovedProcessGraphSchema,
    DraftProcessGraphSchema,
    ReviewDecisionSchema,
    StepSchema,
)
from ..repositories.approved_process_repository import ApprovedProcessRepository
from ..repositories.draft_process_repository import DraftProcessRepository
from ..repositories.review_decision_repository import ReviewDecisionRepository
from ..logger import logger


class ProcessNotFoundError(Exception):
    pass


class InvalidReviewActionError(Exception):
    pass


class ReviewRequiredError(Exception):
    pass


VALID_ACTIONS = {"accept", "modify", "delete", "insert"}


class ReviewService:
    """工艺工程师审核决策 → ApprovedProcessGraph。"""

    def __init__(self, db: Session):
        self.db = db
        self.draft_repo = DraftProcessRepository(db)
        self.approved_repo = ApprovedProcessRepository(db)
        self.review_repo = ReviewDecisionRepository(db)

    def submit_review(
        self, process_id: UUID, decisions: list[ReviewDecisionSchema], reviewer: str = "Engineer"
    ) -> tuple[UUID, ApprovedProcessGraphSchema]:
        """提交审核决策并生成 ApprovedProcessGraph。

        返回 (approved_process_id, ApprovedProcessGraphSchema)。
        """
        logger.info(f"开始处理审核，工艺 ID: {process_id}，决策数: {len(decisions)}")

        # 1. 查询 DraftProcessGraph
        dpg = self.draft_repo.get_by_id(process_id)
        if dpg is None:
            logger.error(f"工艺流程未找到：{process_id}")
            raise ProcessNotFoundError(process_id)

        draft_data = json.loads(dpg.graph_json)
        draft = DraftProcessGraphSchema(**draft_data)

        # 2. 校验决策
        if not decisions:
            raise ReviewRequiredError("至少需要一个审核决策")

        for d in decisions:
            if d.action not in VALID_ACTIONS:
                raise InvalidReviewActionError(f"无效操作: {d.action}")

        # 3. 应用决策到步骤列表
        updated_steps = self._apply_decisions(draft.steps, decisions)

        # 4. 持久化审核决策
        for d in decisions:
            rd = ReviewDecision(
                process_id=str(process_id),
                step_id=str(d.stepId),
                action=d.action,
                reason=d.reason,
                reviewer=reviewer,
            )
            self.review_repo.save(rd)

        # 5. 更新 DraftProcessGraph 状态
        self.draft_repo.update_graph_json(process_id, draft.model_dump_json(), "approved")

        # 6. 创建 ApprovedProcessGraph —— schema 和 DB 使用相同 UUID
        approved_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        approved = ApprovedProcessGraphSchema(
            approvedProcessId=approved_id,
            approvedBy=reviewer,
            approvedAt=now,
            steps=updated_steps,
        )

        apg = ApprovedProcessGraph(
            id=str(approved_id),
            draft_process_id=str(process_id),
            graph_json=approved.model_dump_json(),
            approved_by=reviewer,
            approved_at=now,
        )
        self.approved_repo.save(apg)

        return approved_id, approved

    def _apply_decisions(
        self, steps: list[StepSchema], decisions: list[ReviewDecisionSchema]
    ) -> list[StepSchema]:
        """将审核决策应用到步骤列表。"""
        step_map = {str(s.stepId): s for s in steps}
        result = []

        for d in decisions:
            sid = str(d.stepId)

            if d.action == "accept":
                if sid in step_map:
                    result.append(step_map[sid])

            elif d.action == "delete":
                # 跳过此步骤（不加入结果列表）
                pass

            elif d.action == "modify":
                if sid in step_map:
                    modified = step_map[sid].model_copy(deep=True)
                    modified.title = f"{modified.title} (已修改)"
                    modified.description = d.reason or modified.description
                    result.append(modified)

            elif d.action == "insert":
                new_step = StepSchema(
                    stepId=uuid.uuid4(),
                    sequence=len(result) + 1,
                    title=f"新增步骤",
                    description=d.reason or "工程师插入的步骤",
                    requiredParts=[],
                    requiredTools=[],
                )
                result.append(new_step)

        # 重新编号
        for i, s in enumerate(result, 1):
            s.sequence = i

        return result

    def get_approved(self, approved_process_id: UUID) -> ApprovedProcessGraphSchema | None:
        """根据 ID 获取 ApprovedProcessGraph。"""
        apg = self.approved_repo.get_by_id(approved_process_id)
        if apg is None:
            return None
        data = json.loads(apg.graph_json)
        return ApprovedProcessGraphSchema(**data)
