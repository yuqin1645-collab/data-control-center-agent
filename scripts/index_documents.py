"""创建样本文档并索引到 Chroma (传统 RAG 路径用)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os

DOC_DIR = "data/documents"

SAMPLE_DOCS = {
    "报销流程.md": """# 公司报销流程

## 适用范围
本流程适用于全体员工日常差旅、办公、招待等费用的报销。

## 报销步骤
1. 员工填写报销单, 附上发票原件
2. 直属主管审核签字
3. 部门经理审批 (金额超过 5000 元需总监审批)
4. 财务部复核
5. 打款到工资卡 (一般 5 个工作日内到账)

## 退货处理流程
1. 客户提出退货申请
2. 客服部核实退货原因, 判断是否符合退货政策
3. 符合条件的, 生成退货单
4. 仓储部收货验收
5. 财务退款

## 华东区退货率政策
华东区本月退货率若超过 8%, 需提交退货原因分析报告, 由销售经理和客服经理共同签字。
""",
    "员工手册.md": """# 员工手册

## 考勤制度
工作日 9:00-18:00, 弹性 30 分钟。迟到 3 次以内口头提醒, 超过 3 次扣绩效。

## 请假流程
- 事假: 提前 1 天在系统提交, 主管审批
- 病假: 当天电话告知, 销假时补医院证明
- 年假: 需提前 3 天申请, 当年未休完可结转至次年 3 月

## 奖惩制度
- 月度优秀员工: 奖金 1000 元
- 季度销售冠军: 奖金 5000 元
- 严重违规: 视情节警告/记过/解除合同
""",
    "产品介绍.md": """# 产品线介绍

## 电子类
P001 智能音箱, 售价 499
P002 蓝牙耳机, 售价 299
P003 平板电脑, 售价 2599

## 服装类
P010 男士夹克, 售价 399
P011 女士连衣裙, 售价 459

## 退货政策
电子类产品 7 天无理由退货, 服装类 15 天无理由退货, 食品类不支持退货。
""",
}


def create_docs():
    os.makedirs(DOC_DIR, exist_ok=True)
    for fname, content in SAMPLE_DOCS.items():
        with open(os.path.join(DOC_DIR, fname), "w", encoding="utf-8") as f:
            f.write(content)
    print(f"已创建 {len(SAMPLE_DOCS)} 个样本文档到 {DOC_DIR}")


def index_docs():
    from retrieval.traditional_rag.indexer import index_documents
    n = index_documents(DOC_DIR, collection_name="company_docs")
    print(f"已索引 {n} 个文档到 Chroma")


if __name__ == "__main__":
    create_docs()
    index_docs()
